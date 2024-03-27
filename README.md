## Insider-Trade-Analysis
### Jupyter Notebooks illustrating a data science project to see whether insider trading is measurably reflected in stock price movements.

The main notebook is `Insider_Trade_Detection.ipynb`. You can use it immediately upon download, for demonstation purposes. It assumes the existence of three files in the current working directory:
1. "tickerlist.csv" --- This is simple list of stock ticker symbols, one per line.
2. "insider_buys.csv" --- This file is produced by the notebook `get_insider_buys.ipynb`, which is the main tool for extracting the necessary info from the SEC and processing it for our use. This notbook takes a couple of hours or so to run. A verion of it is included with this distribution, and so **the reader may skip execution of get_insider_buys.ipynb.
3. "lrc_inferred.csv" --- This file is produced by `lateral_predictor.ipynb`. A verion of it is included with this distribution, and so **the reader may skip execution of lateral_predictor.ipynb.

If you wish to change the set of stocks under consideration, simply change `tickerlist.csv`, and then re-run `get_insider_buys.ipynb` and `lateral_predictor.ipynb` to regenerate "insider_buys.csv" and "lrc_inferred.csv". Then re-run `Insider_Trade_Detection.ipynb`.

