import csv
import os
import pandas as pd

def read_tickerlist_csv(filepath='tickerlist.csv'):
    if filepath==None:
        filepath = '/home/jovyan/capstone_dev/tickerlist.csv'
    tickerlist = []
    with open(filepath, 'r', newline='') as f:
        for row in csv.reader(f):
            tickerlist += [s.strip() for s in row]
    return tickerlist

#--------------------------------------

def write_tickerlist_csv(tickerlist, filepath='tickerlist.csv'):
    if filepath==None:
        filepath = '/home/jovyan/capstone_dev/tickerlist.csv'
    with open(filepath, 'w', newline='') as f:
        for row in tickerlist:
            csv.writer(f).writerow([row])
    return ()


#--------------------------
def update_insider_buys_file(buy_list):
    filename = 'insider_buys.csv'
    existing_accession_numbers = set()

    # Check if file exists and read existing accession numbers
    if os.path.exists(filename):
        with open(filename, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            existing_accession_numbers = {row['accession'] for row in reader}

    # Filter buy_list to include only new entries
    new_entries = [entry for entry in buy_list if entry['accession'] not in existing_accession_numbers]

    # Write new entries to file
    if new_entries:
        mode = 'a' if existing_accession_numbers else 'w'
        with open(filename, mode, newline='') as file:
            fieldnames = new_entries[0].keys()
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            if not existing_accession_numbers:  # Write header only if file is new
                writer.writeheader()

            for item in new_entries:
                # Convert list to a string for 'insider_type'
                item['insider_type'] = ', '.join(item['insider_type'])
                writer.writerow(item)
#-----------------------------------------
def read_csv_to_dict_list(file_path):
    with open(file_path, mode='r') as csv_file:
        # Read the file using DictReader which automatically uses the first row as headers
        csv_reader = csv.DictReader(csv_file)

        # Convert each row in the csv file to a dictionary
        dict_list = [row for row in csv_reader]

        # Convert 'insider_type' back from string to list
        for item in dict_list:
            item['insider_type'] = item['insider_type'].split(', ')

    return dict_list
#-----------------------------------------
# Read the saved SEC Form 4 data and convert it to a Dataframe
def read_csv_to_df(start_date):
    insider_buys_dicts = read_csv_to_dict_list('insider_buys.csv')
    insider_buys_df = pd.DataFrame(insider_buys_dicts)

    # Convert some of the columns from strings to more useful types
    insider_buys_df['trade_date'] = pd.to_datetime(insider_buys_df['trade_date'])
    insider_buys_df['filing_date'] = pd.to_datetime(insider_buys_df['filing_date'])
    insider_buys_df['number_shares'] = insider_buys_df['number_shares'].astype(float).astype(int)
    insider_buys_df['price_per_share'] = insider_buys_df['price_per_share'].astype(float)

    # Drop rows before our start date
    insider_buys_df['trade_date'] = insider_buys_df['trade_date'].dt.tz_localize('America/New_York')
    insider_buys_df = insider_buys_df[insider_buys_df['trade_date'] >= start_date]

    # Add a new column, and then sort by that column
    insider_buys_df['cost_of_trade'] = (
        insider_buys_df['number_shares'] * insider_buys_df['price_per_share']).round().astype(int)
    position = insider_buys_df.columns.get_loc('price_per_share') + 1
    insider_buys_df.insert(position, 'cost_of_trade', insider_buys_df.pop('cost_of_trade'))

    insider_buys_df.sort_values(by='cost_of_trade', ascending=False, inplace=True)
    insider_buys_df[['ticker', 'trade_date', 'filing_date','insider_type',  'cost_of_trade']]
    insider_buys_df = insider_buys_df.reset_index(drop=True)

    insider_buys_df['trade_date'] = insider_buys_df['trade_date'].dt.tz_convert('UTC')
    
    return insider_buys_df

    n_insider_buys = len(insider_buys_df)
#-------------------------------------------------------------------------------