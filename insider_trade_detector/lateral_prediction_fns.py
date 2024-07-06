import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


#-------------------------------------------------------------------
def max_canonical_correlation(X, Y):
    '''
    X and Y are assumed here to be already centered! 
    X = X - np.mean(X, axis=0)
    Y = Y - np.mean(Y, axis=0)
    '''
    
    S_xx = np.cov(X.T)
    S_yy = np.cov(Y.T)
    S_xy = np.cov(X.T, Y.T)[:X.shape[1], X.shape[1]:]
    

    return np.max(np.linalg.eig(np.linalg.inv(S_xx)@S_xy@np.linalg.inv(S_yy)@(S_xy.T))[0])
#-------------------------------------------------------------------
def get_ewmcorr_distance(lr_ohlcv_1, lr_ohlcv_2, span=100):
    """
    Calculate the EWMA-based distance (1 - correlation) between the 'lrc' columns 
    of two dataframes representing daily log-returns of closing prices.

    :param lr_ohlcv_1: DataFrame for the first stock, including 'lrc' column.
    :param lr_ohlcv_2: DataFrame for the second stock, including 'lrc' column.
    :param span: Integer, "span" value for EWMA decay.
    :return: EWMA-based distance between the two time series.
    """
    series1 = lr_ohlcv_1['lrc'].values
    series2 = lr_ohlcv_2['lrc'].values

    n = min(len(series1), len(series2))
    alpha = 2 / (span + 1)
    weights = np.array([(1 - alpha)**i for i in range(n)])
    weights /= np.sum(weights)

    weighted_series1 = series1[-n:] * weights
    weighted_series2 = series2[-n:] * weights

    standardized_series1 = (weighted_series1 - np.mean(weighted_series1)) / np.std(weighted_series1)
    standardized_series2 = (weighted_series2 - np.mean(weighted_series2)) / np.std(weighted_series2)

    ewma_corr = np.dot(standardized_series1, standardized_series2) / n

    return 1 - ewma_corr
#-------------------------------------------------------------------
def corr_ewm(multiindexed_df, span=20):
    """
    Calculate the EWMA-based correlation matrix for a given DataFrame with a multi-level index

    :param multiindexed_df: pd DataFrame with a two-level index ('ticker', 'date') and a single column
    :param span: Integer, "span" value for EWMA decay.
    :return: EWMA-based correlation matrix
    """
    # Unstack the DataFrame to have tickers as columns and dates as rows
    unstacked_df = multiindexed_df.unstack(level='ticker')['lrc']

    # Convert to NumPy array for calculations
    local_matrix = unstacked_df.values

    n, m = local_matrix.shape
    alpha = 2 / (span + 1)
    weights = np.array([(1 - alpha)**i for i in range(n)])
    weights /= np.sum(weights)
    weighted_data = local_matrix * weights[:, np.newaxis]
    standardized_data = (weighted_data - np.mean(weighted_data, axis=0)) / np.std(weighted_data, axis=0)
    ewma_corr_matrix = np.dot(standardized_data.T, standardized_data) / n
    
    np.fill_diagonal(ewma_corr_matrix, 1.0)

    return pd.DataFrame(ewma_corr_matrix, index=unstacked_df.columns, columns=unstacked_df.columns)
#-------------------------------------------------------------------
def max_can_corr_distance(lr_ohlcv_1, lr_ohlcv_2):
    return  1-max_canonical_correlation(lr_ohlcv_1, lr_ohlcv_2)
#-------------------------------------------------------------------
def get_distance_matrix(lr_ohlcv_multi):
        
    #distance_metric = max_can_corr_distance
    distance_metric = get_ewmcorr_distance
        
    tickers = lr_ohlcv_multi.index.get_level_values('Ticker').unique()
    n = len(tickers)
    distance_matrix = np.zeros((n, n))

    for i, ticker1 in enumerate(tickers):
        for j, ticker2 in enumerate(tickers[i+1:], start=i+1):
            dist = distance_metric(lr_ohlcv_multi.loc[ticker1], lr_ohlcv_multi.loc[ticker2])
            distance_matrix[i, j] = distance_matrix[j, i] = dist

    return pd.DataFrame(distance_matrix, index=tickers, columns=tickers)
#----------------
def ohlcv_to_z(ohlcv_single):
        
    previous_close = ohlcv_single['Close'].shift(1)
    log_returns = pd.DataFrame({
        #'lro': np.log(ohlcv_single['Open'] / previous_close),
        'lrh': np.log(ohlcv_single['High'] / previous_close),
        'lrl': np.log(ohlcv_single['Low'] / previous_close),
        'lrc': np.log(ohlcv_single['Close'] / previous_close)
    })

    # Filling the NaN values in the first row with zeros
    log_returns.iloc[0] = 0

    #z_volume = pd.Series((ohlcv_single['Volume'] - ohlcv_single['Volume'].mean()) / 
    #                      ohlcv_single['Volume'].std(), 
    #                    name='volume_z')

    # Combining Z-scores for prices and volume
    #z_scores = pd.concat([(log_returns - log_returns.mean()) / log_returns.std(), z_volume], 
    #                     axis=1)

    # Combining Z-scores NOT volume
    #z_scores = pd.concat([(log_returns - log_returns.mean()) / log_returns.std()], axis=1)
    z_scores = log_returns

    return z_scores
    #return log_returns
#----------------
#----------------
def get_start_date(symbol_list, start_date_pad=30):
    earliest_info = {}
    for symbol in symbol_list:
        ticker = yf.Ticker(symbol)
        # Fetch minimal data to find the first available date
        data = ticker.history(period="5d", start="1900-01-01")
        if not data.empty:
            earliest_info[symbol] = data.index[0]

    if earliest_info:
        # Find the ticker with the latest 'first_date_available'
        latest_ticker = max(earliest_info, key=earliest_info.get)
        max_earliest_date = earliest_info[latest_ticker]
        start_date = max_earliest_date + timedelta(days=start_date_pad)  
        return start_date, latest_ticker
    else:
        return None, None  # Or a default start date and a placeholder ticker
#----------------
def find_neighbors( distance_df_local, symb, k=4):
    '''
    Given the distance matrix and a ticker name, 
    return:
        `nearest` (list of string) which is symb's m nearest neighbors 
        `tightness` (float) which is 1.0/(averge distance to a neighbor)
    '''
    
    # For the given ticker symbol, create a list of the m nearest neigbors
    nearest = list(distance_df_local.loc[symb].sort_values().index[1:k+1])
    
    # Sum the distances to the m nearest neighbors. This is a measure of how tight the neightborhood is
    tightness = sum(distance_df_local[symb][s]**2 for s in nearest)/len(nearest)
    tightness = 1/tightness
    
    return nearest, tightness

#--------------------------------------------------------
def plot_target(target_date, ohlcv_target, ohlcv_nbrs, days_fwd):
    '''
    - target_date : A pd. Timestamp object. This is a date on which an insider trade occured for the target stock
    - ohlcv_target : OHLCV pd df for target stock. Indexed by 'Date'
    - ohlcv_nbrs: OHLCV pd df for the neigboring stocks. If there is more than one nbr, then ohlcv_nbrs is multi-indexed, 
            top level 'Ticker',  second, 'Date'
    - days_fwd (int): Plot plot will be produced for the target and each of the neighbors, 
        starting two trading days before "target_date" and ending "target_date + days_fwd"

    A plot is produced showing the relative change of the target and neighbor stocks, closing price, 
    relatative to the target date. All on one plot
    '''
    
    target_date_local = target_date.normalize()
    #print(' ohlcv_target tz is ', ohlcv_target.index.tz)
    #print(' ohlcv_nbrs tz is ', ohlcv_nbrs.index.get_level_values('Date').tz)
    
    # Calculate the start and end dates
    date_index = ohlcv_target.index.get_level_values('Date')
    target_idx = date_index.get_loc(target_date_local)

    start_idx = max(target_idx - 2, 0)  
    normalize_idx = max(target_idx - 1, 0)  
    end_idx = min(target_idx + days_fwd, len(date_index) - 1)  

    start_date = date_index[start_idx]
    normalize_date = date_index[normalize_idx]
    end_date = date_index[end_idx]

  
    #print(start_date, '\t', normalize_date,  '\t',target_date_local,  '\t',end_date)

    # Create a larger plot
    plt.figure(figsize=(15, 8))  
    
    # Normalize and plot the target stock
    target_data = ohlcv_target.loc[start_date:end_date].copy()
    target_data['Normalized_Close'] = target_data['Close'] / target_data.loc[normalize_date, 'Close']
    plt.plot(target_data.index, target_data['Normalized_Close'], label='Target')

    # Process each neighbor stock
    if ohlcv_nbrs.index.nlevels > 1:  # Check for MultiIndex
        for ticker in ohlcv_nbrs.index.get_level_values(0).unique():
            nbr_data = ohlcv_nbrs.xs(ticker, level='Ticker').loc[start_date:end_date].copy()  # Use copy here
            nbr_data['Normalized_Close'] = nbr_data['Close'] / nbr_data.loc[normalize_date, 'Close']
            plt.plot(nbr_data.index, nbr_data['Normalized_Close'], label=ticker, linestyle='--')
    else:
        ohlcv_nbrs = ohlcv_nbrs.loc[start_date:end_date].copy()  # Use copy here
        ohlcv_nbrs['Normalized_Close'] = ohlcv_nbrs['Close'] / ohlcv_nbrs.loc[normalize_date, 'Close']
        plt.plot(ohlcv_nbrs.index, ohlcv_nbrs['Normalized_Close'], label='Neighbor')

    # Add a vertical line at the target date and a horizontal line at 1.0
    plt.scatter(target_date_local, 1.0, color='blue', marker='o', facecolors='red', edgecolors='black', s=100) 


    # Finalize plot
    plt.legend()
    plt.xlabel('Date')
    plt.ylabel('Relative Price Change')
    plt.title('Relative Stock Price Changes')
    plt.show()

#--------------------------------------------------------
#----------------
def feature_transformer(ohlcv_nbrs):

    symbols_nbd = ohlcv_nbrs.index.get_level_values('Ticker').unique()
    n_nbrs = len(symbols_nbd)
    #print(symbols_nbd)

    features = pd.DataFrame()
    for symbol in symbols_nbd:
        features = pd.concat([features, ohlcv_to_z(ohlcv_nbrs.loc[symbol])], axis=1)

    return features.values
#----------------\

