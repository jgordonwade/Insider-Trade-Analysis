import requests
import time
import xml.etree.ElementTree as et

import insider_trade_detector as itd



#------------------------------------------------------------------------------------------------

JGWheader = {"User-Agent": "jgordonwade@protonmail.com"}
cik_dict = None

#------------------------------------------------------------------------------------------------


def ticker_to_cik(ticker_to_find):
    global cik_dict
    
    # Make the API call only if cik_dict is not already populated
    if cik_dict is None:
        print('Making initial call to get ticker-to-cik dictionary')
        url = 'https://www.sec.gov/files/company_tickers.json'
        cik_dict = requests.get(url, headers=JGWheader).json()
        time.sleep(0.1001)
        
    #print(cik_dict)

    matching_entries = [entry for entry in cik_dict.values() if entry.get("ticker") == ticker_to_find]
    if len(matching_entries) != 1:
        print('Problem with CIK numbers')

    cik = str(matching_entries[0]['cik_str'])
    cik = '0' * (10 - len(cik)) + cik
        
    return cik
#--------------------------------------------------------------------------------------------
def parse_insider_element(insider):
    '''
    `insider` is an ElementTree object correpsonding to a given Form 4. 
    
    This function returs data for any "non-derivative" transactions which are insider open-market buys. 
    
    It returns this data in the form of a list of dictionaries called `transactions`, 
    each dict haveing these keys:
        'transactionDate  (string)
        'transactionShares'  (string)
        'transactionPricePerShare' (string)
        'insider_type'  (list of strings)
    '''
    #
    # First go thru and keep only instances of a Form 4 where 
    # an insider reports a purchase of common stock on the open market.  
    trans_objs = insider.findall('.//nonDerivativeTransaction')
    transactions = []
    for k  in range(len(trans_objs)):
        security_title = trans_objs[k].find('.//securityTitle/value').text
        transaction_code = trans_objs[k].find('.//transactionCoding/transactionCode').text
        if 'common' in security_title.lower() and transaction_code.lower()=='p':
            
            transaction_date = trans_objs[k].find('.//transactionDate/value').text
            transactionShares = trans_objs[k].find('.//transactionAmounts/transactionShares/value').text
            transaction_price_per_share = trans_objs[k].find('.//transactionAmounts/transactionPricePerShare/value').text

            transactions.append({
                 'transactionDate' : transaction_date
                ,'transactionShares' : transactionShares
                ,'transactionPricePerShare' : transaction_price_per_share
            })
    # At the end of this loop, if `transactions` is not empty theb it contains a list of dictionaries
    # of instances where an insider reports a purchase of common stock on the open market.
            
    if len(transactions)==0:
        return transactions
    else:
        def is_insider_type(xml_tag):
            rval = False
            is_tag = insider.find(f'.//{xml_tag}')
            if is_tag is not None:
                if is_tag.text == '1':
                    rval = True
            return rval
        insider_tag_list = ['Director', 'Officer', 'TenPercentOwner', 'Other']        
        for d in transactions:
            d['insider_type'] = [t for t in insider_tag_list if  is_insider_type(f'is{t}')]
            
        return transactions

#------------------------------------------------------------
def ticker_to_filing_list(symbol:str)->dict:

    # For a given ticker, get the  URL's for the XML versions of the submissions

    # We get a .json file containing information about all 'recent' SEC filings 
    # that have been made by this CIK/ticker symbol

    # This json file converts cleanly to a dict which I call `response`

    # * `response['filings']['recent']` is a dict with 14 keys. 
    # The value for each key is a list, and all 14 values-lists are the same length, 
    # and that length is the number of filings this company has made. 

    # So for example if we create a variable called `filing_num`, then the 
    # `filing_num`-th entry in each of these 14 lists correspond to what we 
    # can think of as the `filing_num`-th filing by this company. 
    # (I emphasize that this `filing_num` is my own variable, not the SEC's!)  

    #   response['filings'][recent']['accessionNumber'] The accession numbers for all this company's SEC fiings. 
    #   response['filings'][recent']['form'] We're interested in Form 4's, for which this value is simply '4'
    #   response['filings'][recent']['primaryDocument'] The file name of thej XML version of the actual filing. 


    cik = ticker_to_cik(symbol)
    url = 'https://data.sec.gov/submissions/CIK'+cik+'.json'
    print('About to get this url: ', url)
    response = requests.get(url, headers=JGWheader)
    time.sleep(0.1001)
    print('Resonse code: ', response.status_code, response.reason)
    response = response.json()

    recent_filings = response['filings']['recent']

    # `recent filings` is a dict, with the following keys, each of which is a list of strings.
    #     accessionNumber
    #     filingDate
    #     reportDate
    #     acceptanceDateTime
    #     act 
    #     form
    #     fileNumber
    #     filmNumber
    #     items
    #     size 
    #     isXBRL
    #     isInlineXBRL 
    #     primaryDocument 
    #     primaryDocDescription 

    # ---------------

    # Go thru `recent_filings` and get the filing_num's of only Form 4 repprts
    n_filings = len(recent_filings['accessionNumber'])
    form4_indices=[]
    for filing_num in range(n_filings):
        if recent_filings['form'][filing_num] == '4':
            form4_indices = form4_indices+[filing_num]


    # Now build a dict `recent_forms` which is keyed in accession number 
    # and has the data we want in the keys.        
    recent_form4s = []
    count=0
    for index in form4_indices:
        accnum =      recent_filings['accessionNumber'][index]
        trade_date =  recent_filings['reportDate'][index]
        filing_date = recent_filings['filingDate'][index]
        xml_name =    recent_filings['primaryDocument'][index]

        recent_form4s.append({'accession_number': accnum,
                              'ticker': symbol.strip(),
                              'cik': cik,
                              'trade_date': trade_date,
                              'filing_date': filing_date,
                              'xml_name': xml_name})
        #print(recent_form4s[count]['accession_number'])
        count += 1
    return recent_form4s
#------------------------------------------------------------
def filing_to_urls(filing_dict:dict):
    # filing_dict is a dictionary with keys:
    # 'accession_number', 'ticker', 'cik', 'trade_date', 'filing_date', 'xml_name'
    
    cik_full = filing_dict['cik']
    cik = cik_full.lstrip('0')

    accession_full = filing_dict['accession_number']
    accession = accession_full.replace('-','')

    xml_name = filing_dict['xml_name']

    xml_base = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{xml_name}'
    
    # This is a clickable URL, in the sense that if you print it out and paste it into 
    # address field in your browswer, you will see the SEC Form 4 we're scraping. 
    xml_url = xml_base.format(cik=cik, accession=accession, xml_name = xml_name)

    txt_base = f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession_full}.txt'
    txt_url = txt_base.format(cik=cik, accession=accession, accession_full=accession_full)

    return [txt_url, xml_url]
#-------------------------------------------------------------------------
def ticker_to_insider_buys(ticker)->list:
    '''
    - **Input:** A string containing a single  ticker symbol.

    - **Output:** A list (`insider_buys`), where each element is a dictionary containing relevant information about an 
        insider buy transaction. These data include: accession number, ticker, trade and filing dates, number of shares, 
        price per share, insider type, and the URL of the XML filing.

    - **Outline** of  ``ticker_to_insider_buys`
        - Calls `ticker_to_filing_list(ticker)` to get a list of SEC filings (Form 4s) related to the given ticker. 
          This list contains information about each filing, like accession number, trade date, filing date, and the 
          name of the XML file containing the filing's details.

        - Iterates through each filing (Form 4) in the list. For each filing, construct URLs for the text and 
           XML versions of the filing document (`filing_to_urls` function).
    
        - Make a “get” request to retrieve the text version of the filing. From this, extracts and trims the 
          XML portion from the retrieved text. 

        - Then parses the XML using `itd.parse_insider_element`. This function returns a list of dictionaries, 
          each representing an insider buy transaction. These transactions are then appended to the `insider_buys` list.
    '''
        
    filing_dict_list = itd.ticker_to_filing_list(ticker)
    
    estimated_time = len(filing_dict_list)*0.004146 + 0.104709 
    print(f'{len(filing_dict_list)} filings. This loop will take about {estimated_time:.2f} minutes')
    
    tcount=0
    insider_buys = []
    stime = time.time()
    for form4_dict in filing_dict_list:
        '''
        form4_dict has keys: 
            'accession_number'
            'ticker'
            'cik'
            'trade_date'
            'filing_date'
            'xml_name'
        '''

        [txt_addr, xml_addr] = filing_to_urls(form4_dict)

        response = requests.get(txt_addr,headers=JGWheader)
        xml_time_start = time.time()
        tcount += 1
        if tcount%50 == 0:
            print(f'{tcount/len(filing_dict_list):0.3f} of the way thru')

        if response.status_code==200:
            response = response.text
            xml_start = 5+response.find('<XML>')
            xml_end = response.find('</XML>')
            xml_str = response[xml_start:xml_end]
            xml_str = xml_str.strip()

            form4_root = et.fromstring(xml_str)

            transactions = itd.parse_insider_element(form4_root)

            for k in range(len(transactions)):
                insider_buys.append({
                    'accession': form4_dict['accession_number'],
                    'ticker': form4_dict['ticker'],
                    'trade_date': transactions[k]['transactionDate'],
                    'filing_date' : form4_dict['filing_date'],
                    'insider_type': transactions[k]['insider_type'],
                    'number_shares': transactions[k]['transactionShares'],
                    'price_per_share' : transactions[k]['transactionPricePerShare'],
                    'insider_type' : transactions[k]['insider_type'],
                    'xml_url' : xml_addr
                })

        xml_time_sleep = 0.1001 - (time.time()-xml_time_start)
        time.sleep(max([0,xml_time_sleep]))

    print(f'Done. Took {(time.time()-stime)/60:0.2f} minutes')
    
    return insider_buys
#-----------------------------------------------------------------------------------------------

