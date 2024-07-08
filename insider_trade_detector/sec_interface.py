##############################################################################################
import requests
import time
import xml.etree.ElementTree as ET
from  datetime import datetime
import concurrent.futures
import re
import pickle


import insider_trade_detector as itd



#------------------------------------------------------------------------------------------------

JGWheader = {"User-Agent": "jgordonwade@protonmail.com"}
cik_dict = None

#------------------------------------------------------------------------------------------------
def tikcker_list_to_insider_buy_list(symbol_list,earliest_date='1990-12-31'):
    form4_list = []
    for tikr in symbol_list:
        form4_list += itd.ticker_to_filing_list(tikr,earliest_date)
    len(form4_list)

    individual_url_list = [itd.filing_to_urls(form4)[0] for form4 in form4_list]
    print(len(individual_url_list))


    if 2>1:
        time_est = len(individual_url_list)/600
        print(f'This will take at least {len(individual_url_list)/600:0.2f} minutes. Be patient. ')
        start_time = time.time()
        xml_list = itd.fetch_sec_xmls(individual_url_list, rate_limit=10)
        elapsed_time = time.time() - start_time

        print(f'{elapsed_time/60:0.2f} minutes, or {elapsed_time/len(individual_url_list):.3f} seconds per XML URL')

#         print(len(xml_list))
#         s = sum(len(x) for x in xml_list)
#         print(f'{s:,}')
#         #print(xml_list[123])
#
#         with open('xml_list_saved.pkl', 'wb') as f:
#             pickle.dump(xml_list,f)
#
#     with open('xml_list_saved.pkl', 'rb') as f:
#         xml_list = pickle.load(f)
#     print(len(xml_list))

    insider_buy_list = itd.xmls_to_insider_buys(xml_list)

    return insider_buy_list
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

#------------------------------------------------------

def parse_insider_element(insider):
    '''
    `insider` is an ElementTree object correpsonding to a given Form 4. 
    
    This function returns data for any "non-derivative" transactions which are insider open-market buys. 
    
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
            #print(ET.tostring(insider, encoding='unicode'))
            transaction_symbol = insider.find('.//issuerTradingSymbol').text
            transactionShares = trans_objs[k].find('.//transactionAmounts/transactionShares/value').text
            
            transaction_price_per_share_obj = trans_objs[k].find('.//transactionAmounts/transactionPricePerShare/value')
            if transaction_price_per_share_obj==None:
                transaction_price_per_share = 0
            else:
                transaction_price_per_share = transaction_price_per_share_obj.text

            transactions.append({
                 'transactionDate' : transaction_date
                ,'issuerTradingSymbol' : transaction_symbol
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

#------------------------------------------------------------

def ticker_to_filing_list(symbol: str, earliest_date: str = '1999-12-31') -> dict:

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


    earliest_date = datetime.strptime(earliest_date,'%Y-%m-%d')

    cik = ticker_to_cik(symbol)
    url = 'https://data.sec.gov/submissions/CIK'+cik+'.json'
    print('About to get this url: ', url, symbol)
    response = requests.get(url, headers=JGWheader)
    time.sleep(0.1001)
    #print('Resonse code: ', response.status_code, response.reason)
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
        if len(recent_filings['reportDate'][filing_num])>5:
            trade_date = datetime.strptime(recent_filings['filingDate'][filing_num],'%Y-%m-%d')
            if recent_filings['form'][filing_num] == '4' and trade_date>earliest_date:
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

#------------------------------------------------
def fetch_single_xml(url, headers):
    """
    Fetch a single XML from the given URL.

    Parameters:
    url (str): URL to fetch the XML data from.
    headers (dict): Headers to use in the request.

    Returns:
    tuple: URL and the XML content as a string (None if the request fails).
    """
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return url, response.text
    else:
        print(f"Failed to fetch {url}: Status code {response.status_code}")
        return url, None

#-------------------------------------------------------------

def fetch_sec_xmls(individual_url_list, rate_limit=10):
    """
    Fetch XML data from SEC API with throttling.

    Parameters:
    individual_url_list (list): List of URLs to fetch the XML data from.
    rate_limit (int): Number of requests allowed per second.

    Returns:
    list: List of XML contents as strings.
    """
    xml_list = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=rate_limit) as executor:
        future_to_url = {executor.submit(fetch_single_xml, url, headers=JGWheader): url for url in individual_url_list}
        for future in concurrent.futures.as_completed(future_to_url):
            url, xml_content = future.result()
            if xml_content:
                xml_list.append(xml_content)
            
            loop_count = len(xml_list)
            if loop_count % 100 == 0:
                print(f'\t {100 * loop_count / len(individual_url_list):.2f} percent done')
                
            # Throttle requests to rate_limit per second
            time.sleep(1 / rate_limit)

    return xml_list

#-----------------------------------------------
def xmls_to_insider_buys(xml_list):
    insider_buys = []
    for response in xml_list:

        pattern = r'ACCESSION NUMBER:\s+(\d{10}-\d{2}-\d{6})'
        match = re.search(pattern, response)
        if match:
            accession_number = match.group(1)
        else:
            print("Accession Number not found")
                

        match = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", response)
        if match:
            date_time_str = match.group(1)
            filing_date = f"{date_time_str[:4]}-{date_time_str[4:6]}-{date_time_str[6:8]}"
            
            #date_time_obj = datetime.strptime(date_time_str, "%Y%m%d%")
            #date_time_obj = datetime.strptime(date_time_str, "%Y%m%d%H%M%S")

        else:
            print("Date-time string not found in the response.")
        
        xml_start = 5+response.find('<XML>')
        xml_end = response.find('</XML>')
        xml_str = response[xml_start:xml_end]
        xml_str = xml_str.strip()
        
        form4_root = ET.fromstring(xml_str)

        transactions = parse_insider_element(form4_root)
        #print(transactions)
        
        for k in range(len(transactions)):
            ticker = transactions[k]['issuerTradingSymbol']
            insider_buys.append({
                'accession': accession_number,
                'ticker': ticker,
                'trade_date': transactions[k]['transactionDate'],
                'filing_date' : filing_date,
                'insider_type': transactions[k]['insider_type'],
                'number_shares': transactions[k]['transactionShares'],
                'price_per_share' : transactions[k]['transactionPricePerShare'],
                'insider_type' : transactions[k]['insider_type'],
                })


    return insider_buys

######################################################

