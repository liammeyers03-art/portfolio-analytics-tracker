import pandas as pd 
import yfinance as yf
import matplotlib.pyplot as plt

path = "Portfolio Tracker.xlsx"  
df = pd.read_excel(path)
tunnel = "TransactionsHistory.xlsx"
transaction_df = pd.read_excel(tunnel)

# =========================
# PRICING LAYER
# =========================

def Pricing(df): 
    Equity_List = df["AssetType"].isin(["Equity","Cash Equivalent"])
    Ticker_List = df[Equity_List]["Ticker"]
    Ticker_List = list(set(Ticker_List))
    Ticker = yf.download(Ticker_List)
    Price = Ticker["Close"].iloc[-1]
    dct = dict(Price)
    df["LivePrice"] = df["Ticker"].map(dct)
    df["UsedPrice"] = df["LivePrice"] 
    df.loc[df["LivePrice"].isna(), "UsedPrice"] = df["CurrentPrice"]
    df.loc[df["AssetType"] == "Option", "UsedPrice"] = df["CurrentPrice"]
    df.loc[df["AssetType"] == "Cash", "UsedPrice"] = df["CurrentPrice"]
    return df

# =========================
# CALCULATION LAYER
# =========================

def Calculations(df):
    #Portfolio Calculations
    df["EffectiveShares"] = df["Shares"] 
    df.loc[df["AssetType"] == "Option", "EffectiveShares"] = df["Contracts"] * df["Multiplier"]
    df["CostBasis"] = df["EntryCost"] * df["EffectiveShares"] 
    df["PositionValue"] = df["EffectiveShares"] * df["UsedPrice"]  
    df["UnrealizedP&L"] = df["PositionValue"] - df["CostBasis"] 
    #Portfolio Metrics
    total_portfolio_value = df["PositionValue"].sum()
    df["PortfolioWeight"] = df["PositionValue"] / total_portfolio_value 
    df["ReturnPct"] = df["UnrealizedP&L"] / df["CostBasis"] 
    return df

# =========================
# ANALYTICS LAYER
# =========================

#Portfolio Stats Analytics Function 
def Get_position_summary(df):
    Total_Positions = ~df["AssetType"].isin(["Cash","Cash Equivalent"])
    Total_Positions = len(set(df[Total_Positions]["Ticker"]))
    Equities = df["AssetType"] == "Equity"
    Equities = len(set(df[Equities]["Ticker"]))
    Options = df["AssetType"] == "Option"
    Options = len(set(df[Options]["Ticker"]))
    Sectors = ~df["AssetType"].isin(["Cash","Cash Equivalent"])
    Sectors = len(set(df[Sectors]["Sector"]))
    Mean_Size = df["AssetType"] != "Cash"
    Mean_Size = df[Mean_Size]["PortfolioWeight"].mean()
    filter = df[df["AssetType"] != "Cash"]
    Largest_Position_Size = filter.nlargest(1,"PortfolioWeight")[["PortfolioWeight"]]

    return Total_Positions, Equities, Options, Sectors, Mean_Size, Largest_Position_Size


#Get PNL Componetns Analytics Function
def Get_pnl_components(transaction_df):
    fees_expenses = transaction_df.groupby("Action")["CostBasis"].sum()
    fees_expenses = fees_expenses["FEES & EXPENSES"]
    filter = transaction_df[transaction_df["Action"] == "SELL"] 
    realizedytd = filter["Proceeds"].sum() - filter["CostBasis"].sum() - fees_expenses
    income = transaction_df.groupby("Action")["Proceeds"].sum()
    income = income["DIVIDEND"]
    return realizedytd, income, fees_expenses

#YTD Performance Analytics Function
def Get_ytd_performance(df,transaction_df,History_df,income,fees_expenses):
    BeginningValue = 13841.74
    accuredincome = 7.29
    EndingValue = df["PositionValue"].sum() 
    withdrawals = transaction_df.groupby("Action")["Proceeds"].sum()
    withdrawals = withdrawals["WITHDRAWAL"]
    deposits = transaction_df.groupby("Action")["Proceeds"].sum()
    deposits = deposits["DEPOSIT"]
    NetContribution = deposits - withdrawals
    InvestmentChange = (EndingValue-BeginningValue-NetContribution) 
    InvestmentG_L = (EndingValue-BeginningValue-NetContribution-income-fees_expenses)
    SPYbeginngingprice = 681.92
    SPYprice = yf.download("SPY")["Close"].squeeze().iloc[-1]
    risk_free = 0.04
    port = History_df["DailyPercentChange"].iloc[1:] / 100
    spy = History_df["SPYDailyPercentChange"].iloc[1:] / 100
    spy_variance = spy.var()
    covariance = spy.cov(port)
    beta = covariance / spy_variance
    capm = risk_free + beta * ((History_df["SPY_Cumulative_Return"].iloc[-1]) - risk_free)
    actual_return = History_df["Port_Cumulative_Return"].iloc[-1]
    return BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, SPYbeginngingprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome

#Benchmark Comparsion Analytics Function
def Get_Benchmark_Comparison(History_df):
    cumulativealpha = History_df["DailyAlpha"].sum()
    cumulativeport = History_df["DailyPercentChange"].sum()
    cumulativeSPY = History_df["SPYDailyPercentChange"].sum()
    win = 0
    loss = 0
    for i in range(1,len(History_df)):
        if History_df["DailyPercentChange"].iloc[i] > History_df["SPYDailyPercentChange"].iloc[i]: 
            History_df.loc[History_df.index[i],"Win/LoseCounter"] = 1 
            win += 1
        elif History_df["DailyPercentChange"].iloc[i] < History_df["SPYDailyPercentChange"].iloc[i]:
            History_df.loc[History_df.index[i],"Win/LoseCounter"] = 0.0
            loss += 1
        else:
            History_df.loc[History_df.index[i],"Win/LoseCounter"] = 0.0
    WinLosepercent = float(win/(win+loss))
    TotalDays = win + loss
    return cumulativealpha, cumulativeport, cumulativeSPY, win, WinLosepercent, TotalDays

#Risk Metrics Analytics Function
def Get_Risk_Metrics(History_df):
    risk_free_rate = 0 
    average_return = History_df["DailyPercentChange"].iloc[1:].mean() / 100
    port_std = History_df["DailyPercentChange"].iloc[1:].std() / 100
    spy_std = History_df["SPYDailyPercentChange"].iloc[1:].std() / 100
    sharpe_ratio = (average_return - risk_free_rate) / port_std
    port = History_df["DailyPercentChange"].iloc[1:] / 100
    spy = History_df["SPYDailyPercentChange"].iloc[1:] / 100
    spy_variance = spy.var()
    covariance = spy.cov(port)
    beta = covariance / spy_variance  
    returns = History_df["DailyPercentChange"] / 100
    neg_returns = returns[returns < 0.00]
    if neg_returns.empty or len(neg_returns) < 2:
        sortino_ratio = 0
    else:
        downsidedev = neg_returns.std()
        sortino_ratio = average_return/downsidedev
    correlation = covariance /(port_std * spy_std)

    return port_std, sharpe_ratio, beta, sortino_ratio, correlation

#Performance Extremes Analytics Function
def Get_Performance_Extremes(History_df):
    Best_day = History_df["DailyPercentChange"].idxmax()
    best_day = History_df.loc[Best_day, ["DailyPercentChange","P/L Day"]]
    Worst_day = History_df["DailyPercentChange"].idxmin()
    worst_day = History_df.loc[Worst_day, ["DailyPercentChange","P/L Day"]]
    return Best_day, best_day, Worst_day, worst_day

#Total Exposure by AssetType Analytics Function
def Get_Asset_Exposure(df):
    Asset_Exposure = df.groupby("AssetType")["PositionValue"].sum() / df["PositionValue"].sum()
    return Asset_Exposure

#Sector Allocation Analytics Function
def Get_Sector_Allocation(df):
    Sector_Allocation = (df.groupby("Sector")["PositionValue"].sum() / df["PositionValue"].sum()).sort_values(ascending=False)
    return Sector_Allocation

#Top Holdings/Concentration Analytics Function 
def Get_Top_Holdings(df):
    filter = ~df["AssetType"].isin(["Cash", "Cash Equivalent"])
    filtered_df = df[filter]
    Top_Holdings = filtered_df.nlargest(5, "PortfolioWeight")[["Ticker","PositionValue","PortfolioWeight"]]
    Concentration = Top_Holdings["PortfolioWeight"].sum()
    return Top_Holdings, Concentration

#Top Movers Analytics Function
def Get_Top_Movers(df):
    top_contributors = df.nlargest(3,"UnrealizedP&L")[["Ticker","UnrealizedP&L","ReturnPct"]]
    top_detractors = df.nsmallest(3, "UnrealizedP&L")[["Ticker","UnrealizedP&L","ReturnPct"]]
    return top_contributors, top_detractors

#Fundementals 
def Get_Investment_Fundementals(df):
    Equity_List = df["AssetType"].isin(["Equity","Option"])
    Ticker_list = df[Equity_List]["Ticker"].unique()
    results = []
    for i in Ticker_list: 
        ticker = yf.Ticker(i)
        info = ticker.info
        trailing_pe = info.get("trailingPE")
        foward_pe = info.get("forwardPE")
        earnings_growth = info.get("earningsGrowth")
        if earnings_growth is not None and earnings_growth != 0:
            earnings_growth = earnings_growth * 100
            peg = (foward_pe/earnings_growth)
        else:
            peg = None
        roe = info.get("returnOnEquity")
        beta = info.get("beta")
        dct = {"Ticker":i,"TrailingPE":trailing_pe,"ForwardPE":foward_pe,"EarningsGrowth":earnings_growth,"PEG":peg,"ROE":roe,"Beta":beta}
        results.append(dct)
    results = pd.DataFrame(results)
    return results 
    

#Risk Flags Analytics Function 
def Get_risk_flags(df):
    portfolio_concentration = (df["PortfolioWeight"] > .10) & (df["AssetType"] != "Cash")
    sector_concentration = (df.groupby("Sector")["PositionValue"].sum()) / df["PositionValue"].sum()
    sector_concentration = sector_concentration[sector_concentration > .35]
    severe_drawdown = df["ReturnPct"] < -.25
    option_concentration = df[df["AssetType"] == "Option"]
    option_concentration = option_concentration["PortfolioWeight"].sum()
    return portfolio_concentration, sector_concentration, severe_drawdown, option_concentration
 
    
# =========================
# History Tracker
# =========================

def Get_Portfolio_History(df):
    Filter = (df[df["AssetType"] != "Cash"])
    Today = pd.to_datetime("today").date()
    TotalPortfolioValue = df["PositionValue"].sum()
    FilteredPortfolioValue = Filter["PositionValue"].sum()
    TotalUnrealizedPL = df["UnrealizedP&L"].sum()
    TotalCostBasis = Filter["CostBasis"].sum()
    PortfolioReturnPct = (FilteredPortfolioValue - TotalCostBasis)/TotalCostBasis * 100
    return Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct

def Get_Today_SPY_Close():
    latest_price = yf.download("SPY")["Close"].squeeze().iloc[-1]
    date = yf.download("SPY")["Open"]
    latest_date = date.index[-1]
    latest_date = latest_date.date()
    return latest_price,latest_date

def Save_Portfolio_History(Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct, latest_price, latest_date):
    road = "HistoryTracker.xlsx"
    History_df = pd.read_excel(road)
    History_df["Date"] = pd.to_datetime(History_df["Date"]).dt.date
    new_row = {"Date":Today,"PortfolioValue":TotalPortfolioValue,"UnrealizedPL":TotalUnrealizedPL,"UnrealizedReturnPct":PortfolioReturnPct,"SPYCLOSE":latest_price}
    new_row_df = pd.DataFrame([new_row])
    matching_dates = History_df["Date"] == Today
    if Today == latest_date:
        if matching_dates.any():
            History_df.loc[History_df["Date"] == Today, ["PortfolioValue","UnrealizedPL","UnrealizedReturnPct","SPYCLOSE"]] = [TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct,latest_price]
        else:
            History_df = pd.concat([History_df,new_row_df],ignore_index=True)
    History_df.to_excel(road,index=False)
    return History_df

def Upgrade_History_df(History_df,transaction_df):
    #Netflow 
    History_df = History_df.set_index("Date")
    multipler = {"WITHDRAWAL":-1,"DEPOSIT":1}
    transaction_df["Multipler"] = transaction_df["Action"].map(multipler)
    transaction_df["Multipler"] = transaction_df["Multipler"].fillna(0)
    transaction_df["NetFlow"] = transaction_df["Proceeds"] * transaction_df["Multipler"]
    net_flow = transaction_df.groupby("Date")["NetFlow"].sum()
    History_df["NetFlow"] = net_flow
    History_df["NetFlow"] = History_df["NetFlow"].fillna(0)

    #P/L Daily in terms of $
    History_df["P/L Day"] = 0.0 
    for i in range(1,len(History_df)):
        A = i
        B = i - 1 
        PL_Day = (History_df["PortfolioValue"].iloc[A] - History_df["PortfolioValue"].iloc[B] - History_df["NetFlow"].iloc[A])
        PL_Day = round(PL_Day,2)
        History_df.loc[History_df.index[A], "P/L Day"] = PL_Day

    #Daily Portfolio Percent Change
    History_df["DailyPercentChange"]  = 0.00
    for i in range (1,len(History_df)):
        A = i
        B = i -1 
        percentchange = (History_df["PortfolioValue"].iloc[A] - History_df["PortfolioValue"].iloc[B] - History_df["NetFlow"].iloc[A]) / History_df["PortfolioValue"].iloc[B] * 100
        percentchange = round(percentchange,2)
        History_df.loc[History_df.index[A],"DailyPercentChange"] = percentchange 
    daily_return = (1 + (History_df["DailyPercentChange"] / 100)).cumprod() - 1 
    History_df["Port_Cumulative_Return"] = daily_return

    #Daily SPY Percent Change and Cumulaitve Change
    History_df["SPYDailyPercentChange"] = 0.00
    for i in range(1,len(History_df)):
        A = i
        B = i - 1 
        percentchange = (History_df["SPYCLOSE"].iloc[A] - History_df["SPYCLOSE"].iloc[B]) / History_df["SPYCLOSE"].iloc[B] * 100
        percentchange = round(percentchange,2)
        History_df.loc[History_df.index[A],"SPYDailyPercentChange"] = percentchange
    SPY_daily_return = (1 + (History_df["SPYDailyPercentChange"] / 100)).cumprod() - 1 
    History_df["SPY_Cumulative_Return"] = SPY_daily_return

    #ALPHA and Win/Loss Counter
    History_df["DailyAlpha"] = History_df["DailyPercentChange"] - History_df["SPYDailyPercentChange"]
    History_df["Win/LoseCounter"] = 0.00
    
    #Drawdown 
    History_df["RunningPeak"] = History_df["PortfolioValue"].cummax()
    History_df["Drawdown"] = 0.0
    Drawdown =  (History_df["PortfolioValue"] - History_df["RunningPeak"]) / History_df["RunningPeak"] * 100 
    Drawdown = round(Drawdown,2)
    History_df["Drawdown"] = Drawdown
  
    return History_df

# =========================
# ASSET RETURN MATRIX
# =========================
def Get_Information(): 
    Today = pd.to_datetime("today").date()
    open_dates = yf.download("SPY")["Open"]
    latest_date = open_dates.index[-1]
    latest_date = latest_date.date()

    path = "AssetReturnMatrix.xlsx"
    Matrix_df = pd.read_excel(path)
    Matrix_df["Date"] = pd.to_datetime(Matrix_df["Date"]).dt.date

    Equity_List = df["AssetType"].isin(["Equity","Cash Equivalent"])
    Equity_List = list(df[Equity_List]["Ticker"])
    Ticker = yf.download(Equity_List)

    Daily_Return_Data = Ticker["Close"].pct_change().iloc[-1]
    new_row = pd.DataFrame(Daily_Return_Data).T
    new_row.insert(0,"Date",Today)
    
    matching_dates = Matrix_df["Date"] != Today
    if Today == latest_date:
        if matching_dates.any():
            Matrix_df = pd.concat([Matrix_df,new_row],ignore_index=True)
        Matrix_df.to_excel(path,index=False)
    print(Matrix_df)

# =========================
# OUTPUT LAYER
# =========================

#Position Summary Stats Output Function 
def position_summary_Output(Total_Positions, Equities, Options, Sectors, Mean_Size, Largest_Position_Size):
    print("Portfolio Stats\n" + "-" * 25)
    print(f"{"Positions:"} {Total_Positions}")
    print(f"Equities: {Equities}")
    print(f"Options: {Options}")
    print(f"Sectors: {Sectors}")
    print(f"Average Position Size: {Mean_Size * 100:.2f}%")
    for index, row in Largest_Position_Size.iterrows():   
        print(f"Largest Position Size: {row["PortfolioWeight"] * 100:.2f}%")
    
#Portfolio Summary Output Function
def PortfolioSummary(df):
    print("Portfolio Summary\n"+ "-" * 25)
    filter = (df[df["AssetType"] != "Cash"])
    print(f"{'Total Portfolio Value:':<24} ${df["PositionValue"].sum():>9,.2f}")
    print(f"{'P/L Open:':<24} {f'${df["UnrealizedP&L"].sum():,.2f}':>10}")

#YTD Performance Output Function
def ytd_performance_output(BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, income, fees_expenses,SPYbeginningprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome):
    print("YTD Performance\n" + '-' * 25)
    print(f"{'Beginning Value:':<22} {f'${BeginningValue:,.2f}':>12}")
    print(f"{'   Contributions':<24} {f'+${deposits:,}':>10}")
    print(f"{'   Withdrawals':<24} {f'-${withdrawals:,}':>10}")
    print(f"{'Net Contributions:':<22} {f'${NetContribution:,.2f}':>12}")
    if InvestmentG_L > 0:
        print(f"{'   Investment G/L':<24} {f'+${InvestmentG_L:,.2f}':>10}")
    else:
        print(f"{'   Investment G/L':<24} {f'{InvestmentG_L:,.2f}':>10}")
    print(f"{'   Income':<24} {f'+${income}':>10}")
    print(f"{'   Fees & Expenses':<24} {f'${fees_expenses}':>10}")
    print(f"{'Investment Change:':<22} {f'${InvestmentChange:,.2f}':>12}")
    print(f"{'   Market Value':<24} {f'${EndingValue:,.2f}':>10}")
    print(f"{'   Accured Income':<24} {f'${accuredincome}':>10}")
    print(f"{'Ending Value:':<22} {f'${EndingValue + accuredincome:,.2f}':>12}")
    print()
    print("Perfromance vs Benchmark\n" + "-" * 25)
    print(f"{"Portfolio Return (TWR):":<27} {f'{actual_return * 100:.2f}%':>7}")
    print(f"{'Simple Return YTD:':<27} {InvestmentChange/BeginningValue * 100:>6.2f}%")
    print(f"{'Benchmark (SPY YTD):':<26} {(SPYprice - SPYbeginningprice) / SPYbeginningprice * 100:>7.2f}%")
    print(f"{'Alpha (TWR):':<24} {f'{(actual_return * 100) - ((SPYprice - SPYbeginningprice) / SPYbeginningprice) * 100:.2f}%':>10}")
    print(f"{'CAPM Expected Return:':<29} {capm * 100:.2f}%")
    print(f"{'Alpha (CAPM):':<24} {f'{(actual_return - capm) * 100:.2f}%':>10}")

#Return Attribution Output Function
def return_attribution_Output(realizedytd,income,fees_expenses,accuredincome):
    print("P&L Attribution\n" +  "-" * 25)
    filter = (df[df["AssetType"] != "Cash"])
    total_return = fees_expenses + realizedytd + income + accuredincome + filter["UnrealizedP&L"].sum()
    print(f"{'Unrealized:':<24} {f'${df["UnrealizedP&L"].sum():,.2f}':>10} {f'(+{(df["UnrealizedP&L"].sum() / total_return)* 100:.0f}%)':>10}")
    print(f"{'Realized:':<25}{f'${realizedytd:,.2f}':>10} {f'({(realizedytd / total_return) * 100:.0f}%)':>10}")
    print(f"{'Income:':<29}${income} {f'(+{(income/total_return) * 100:.0f}%)':>10}")
    print(f"{'Accured Income:':<29} {f'${accuredincome}'} {f'(+{(accuredincome/total_return) * 100:.0f}%)':>10}")
    print(f"{'Fees & Expenses:':<28} ${fees_expenses:>5.2f} {f'({(fees_expenses/total_return) * 100:.0f}%)':>10}")
    print("-" * 25)
    print(f"{'Total:':<25} {f'${total_return:,.2f}':<9} {f'({(total_return/total_return)* 100:.0f}%)':>10}")

#Bench Mark Comparison Output Function
def Benchmark_Comparison_Output(cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays,History_df):
    print("Daily Performance vs SPY\n" + "-" * 38)
    print(f"{'Date':<10} {'Port %':>9} {'SPY %':>14} {'Alpha':>14}\n" + "-" * 48)
    for index,row in History_df[["DailyPercentChange","SPYDailyPercentChange","DailyAlpha"]].iterrows():
        print(f"{str(index):<10} {row["DailyPercentChange"]:>8}% {row["SPYDailyPercentChange"]:>13}% {row["DailyAlpha"]:>13.2f}%" )
    print("-" * 48)
    print(f"Cumulative:{cumulativeport:>8.2f}% {cumulativeSPY:>13.2f}% {cumulativealpha:>13.2f}%") 
    print(f"Win Rate vs SPY: {WinLosepercent * 100:.2f}% ({win}/{TotalDays})") 

#Risk Metrics Output Function
def Risk_Metrics_Output(port_std,sharpe_ratio,beta,History_df,sortino_ratio,correlation):
    print("Portfolio Risk\n" + '-' * 25)
    print(f"{'Daily Volatility:':<18} ±{port_std * 100:.2f}%")
    print(f"{'Correlation:':<21}{correlation:.2f}")
    print(f"{'Sharpe Ratio:':<20} {sharpe_ratio:.2f}")
    print(f"{'Sortino Ratio:':<21}{sortino_ratio:.2f}")
    print(f"{'Beta:':<20} {beta:.2f}")
    print(f"{'Current Drawdown:':<15} {f'{(History_df["Drawdown"].iloc[-1]):.2f}%':>7}")
    print(f"{'Max Drawdown:':<16} {f'{(History_df["Drawdown"].min()):.2f}%':>8}")
    Drawdown_Duration = 0
    for i in History_df["Drawdown"][::-1]:    
        if i < 0.0:
            Drawdown_Duration += 1 
        else:
            break
    print(f"{'Drawdown Duration:':<15} {f'{Drawdown_Duration}':>5}d")

    
#Performance Extremes Output Function
def Performance_Extremes_Output(Best_day, best_day, Worst_day, worst_day):
    print("Performance Extremes\n" + "-" *25)
    print("Best Day:")
    print(f"{str(Best_day):<10} | +{best_day["DailyPercentChange"]:<4}% | +${best_day["P/L Day"]:<8}")
    print()
    print("Worst Day:")
    print(f"{str(Worst_day):<10} | {worst_day["DailyPercentChange"]:<4}% | ${worst_day["P/L Day"]:<8}")
    
#Total Expsoure by AssetType Output Function 
def Asset_Exposure_Output(Asset_Exposure):  
    print("Portfolio Asset Exposure\n"+ "-" * 25)
    print(f"{'Class':<10}{'Weight':>25}")
    print("-" * 38)
    print(f"Equity Allocation: {Asset_Exposure["Equity"]*100:>15.2f}%")
    print(f"Option Allocation: {Asset_Exposure["Option"]*100:>15.2f}%")
    print(f"Cash Equivalent Allocation: {Asset_Exposure["Cash Equivalent"] * 100:>6.2f}%")
    print(f"Cash Allocation: {Asset_Exposure["Cash"]*100:>17.2f}%")

#Sector Allocation Output Function
def Sector_Allocation_Output(Sector_Allocation):
    print("Sector Allocation\n"+ "-" * 25)
    print(f"{'Sector':<10}{'Weight':>25}")
    print("-" * 38)
    for sector,percent in Sector_Allocation.items():
         print(f"{sector:<25}{percent * 100:>9.2f}%")

#Top Holdings/Concentration Output Function 
def Top_Holdings_Output(Top_Holdings, Concentration):
    print("Top Holdings\n"+ "-" * 25)
    print(f"{'Ticker':<10}{'PositionValue':^15}{'Weight':>10}")
    print("-" * 38)
    for index,row in Top_Holdings.iterrows():
        print(f"{row['Ticker']:<13}${row['PositionValue']:<7.2f}{row['PortfolioWeight']*100:>13.2f}%")

#Top Movers Output Function
def Top_Movers_Output(top_contributors,top_detractors,):
    print("Top Movers\n" + "-" * 25)
    print(f"{'Ticker':<9} {'P&L':<6} {'Contrib%':<10} {'Return%'}")
    print("-" * 38)
    for index,row in top_contributors.iterrows():
        print(f"{row["Ticker"]:<5} {f'+${row["UnrealizedP&L"]:.2f}':>9} {f'+{(row["UnrealizedP&L"] / df["UnrealizedP&L"].sum()) * 100:.2f}%':>9} {f'{row['ReturnPct']*100:.2f}%':>9}")
    print()
    for index,row in top_detractors.iterrows():
        print(f"{row["Ticker"]:<5} {f'${row["UnrealizedP&L"]:.2f}':>9} {f'{(row["UnrealizedP&L"] / df["UnrealizedP&L"].sum()) * 100:.2f}%':>9} {f'{row['ReturnPct']*100:.2f}%':>9}")

#Invesment Fundementals Output Function 
def Investment_Fundementals_Ouput(results):
    print("Investment Fundementals\n" + "-" * 25)
    print(f"{'Ticker':<9}{'PE(T)':<9}{'PE(F)':<10}{'ROE':<9}{'Beta':<9}")
    print("-" * 48)
    for row in results.itertuples():
        print(f"{row.Ticker:<6}{row.TrailingPE:>8.2f}{row.ForwardPE:>9.2f}{f'{row.ROE * 100:.2f}%':>10}{row.Beta:>8.2f}")
    

#Risk Flags Output Function 
def risk_flags_Output(portfolio_concentration,sector_concentration,severe_drawdown,option_concentration):
    print("Risk Flags\n" + "-" * 25)
    has_warnings = portfolio_concentration.any() or sector_concentration.any() or severe_drawdown.any() or option_concentration > .10
    if portfolio_concentration.any():
        for index,row in df[portfolio_concentration][["Ticker","PortfolioWeight"]].iterrows():
            print(f"🚨 {row["Ticker"]} at {row["PortfolioWeight"] * 100:.2f}% of portfolio")
    if sector_concentration.any():
        for index,row in sector_concentration.items():
            print(f"🚨 {index}at {row * 100:.2f}% (high concentration) ")
    if severe_drawdown.any():
        for index,row in df[severe_drawdown][["Ticker","ReturnPct"]].iterrows():
            print(f"🚨 {row['Ticker']} is down {row["ReturnPct"]*100:.2f}% from cost basis")
    if option_concentration > .10:
        print(f"🚨 Option Concentration is at {option_concentration * 100:.2f}%")
    if not has_warnings:
        print("No Active Warnings")
    
#Missing Live Prices Output Function
def Missing_Live_Prices(df):
    print("Missing Live Prices\n"+ "-" * 25)
    mask = (df["LivePrice"].isna()) & (df["AssetType"] == "Equity")
    if mask.any():
        for ticker in df[mask]["Ticker"]:
            print(ticker)
    else:
        print("No Missing Prices")
    
#Chat Plotting Output Function 
def Chart_data_Output(History_df,df):
    fig, axes = plt.subplots(1,2, figsize=(12,5))
    fig.set_facecolor('white')
    plt.grid(True, color ='gray')

    #Portfolio Return vs. SPY
    axes[0].plot(History_df["Date"], History_df["Port_Cumulative_Return"] * 100)
    axes[0].plot(History_df["Date"], History_df["SPY_Cumulative_Return"] * 100)
    axes[0].set_title("Portfolio vs SPY Performance")
    axes[0].set_ylabel("Return (%)")
    axes[0].set_xlabel("Date")
    axes[0].legend(["Portfolio","SPY"])

    #Sector Allocation Breakdown 
    sector_allocation = df.groupby("Sector")["PositionValue"].sum() / df["PositionValue"].sum()
    sector_allocation = sector_allocation.sort_values(ascending=True)
    axes[1].pie(sector_allocation, labels=sector_allocation.index, autopct='%1.2f%%')
    axes[1].set_title("Sector Allocation")

    plt.tight_layout()
    plt.show()

   


# =========================
# EXECUTION LAYER
# =========================



def Execution(df,transaction_df):
    df = Pricing(df)
    df = Calculations(df)


    Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct = Get_Portfolio_History(df)
    latest_price, latest_date = Get_Today_SPY_Close()
    History_df = Save_Portfolio_History(Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct, latest_price, latest_date)
    History_df = Upgrade_History_df(History_df,transaction_df)
    results = Get_Investment_Fundementals(df)

    Total_Positions,Equities, Options, Sectors, Mean_Size, Largest_Position_Size = Get_position_summary(df)
    realizedytd,income,fees_expenses = Get_pnl_components(transaction_df)
    BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, SPYbeginningprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome = Get_ytd_performance(df,transaction_df,History_df,income,fees_expenses)
    cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays = Get_Benchmark_Comparison(History_df)
    port_std, sharpe_ratio, beta, sortino_ratio,correlation =  Get_Risk_Metrics(History_df)
    Best_day, best_day, Worst_day, worst_day = Get_Performance_Extremes(History_df)
    Asset_Exposure = Get_Asset_Exposure(df)
    Sector_Allocation = Get_Sector_Allocation(df)
    Top_Holdings,Conentration = Get_Top_Holdings(df)
    top_contributors,top_detractors, = Get_Top_Movers(df)
    portfolio_concentration,sector_concentration,severe_drawdown,option_concentration = Get_risk_flags(df) 

    position_summary_Output(Total_Positions,Equities, Options, Sectors, Mean_Size, Largest_Position_Size)
    print()
    PortfolioSummary(df)
    print()
    ytd_performance_output(BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, income, fees_expenses, SPYbeginningprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome)
    print()
    return_attribution_Output(realizedytd,income,fees_expenses,accuredincome)
    print()
    Benchmark_Comparison_Output(cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays,History_df)
    print()
    Risk_Metrics_Output(port_std,sharpe_ratio,beta,History_df,sortino_ratio,correlation)
    print() 
    Performance_Extremes_Output(Best_day, best_day, Worst_day, worst_day)
    print()
    Asset_Exposure_Output(Asset_Exposure)
    print()
    Sector_Allocation_Output(Sector_Allocation)
    print()
    Top_Holdings_Output(Top_Holdings,Conentration)
    print()
    Top_Movers_Output(top_contributors,top_detractors)
    print()
    Investment_Fundementals_Ouput(results)
    print()
    risk_flags_Output(portfolio_concentration,sector_concentration,severe_drawdown,option_concentration)
    print()
    Missing_Live_Prices(df)
    print()
    print(History_df)
    print()
    # Chart_data_Output(History_df,df)

Get_Information()
# Execution(df,transaction_df)




