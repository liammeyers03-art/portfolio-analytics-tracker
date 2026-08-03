import pandas as pd 
import yfinance as yf
import matplotlib.pyplot as plt
import datetime
import numpy as np
from scipy.optimize import minimize

BASE_PATH = r"C:\Users\liamm\OneDrive\Analytics\Python Projects\QuantTerminal\Portfolio Tracker"

path = BASE_PATH + r"\portfolio_tracker_data.xlsx"
df = pd.read_excel(path, sheet_name='Holdings')
df['Ticker'] = df['Ticker'].astype(str).str.strip().str.upper()
arbitrage_df = pd.read_excel(path,sheet_name='Arbitrage Holdings')


tunnel = BASE_PATH + r"\transaction_data.xlsx"
transaction_df = pd.read_excel(tunnel,sheet_name='Transactions')
arbitrage_transaction_df = pd.read_excel(tunnel,sheet_name='Arbitrage Transactions')

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
    Total_Positions = df["AssetType"] != "Cash"
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
    if (transaction_df['Action'] == 'FEES & EXPENSES').any():
        fees_expenses = transaction_df.groupby("Action")["CostBasis"].sum()
        fees_expenses = fees_expenses["FEES & EXPENSES"]
    else:
        fees_expenses = 0
    filter = transaction_df[transaction_df["Action"] == "SELL"] 
    realizedytd = filter["Proceeds"].sum() - filter["CostBasis"].sum() - fees_expenses
    if (transaction_df['Action'] == 'DIVIDEND').any():
        income = transaction_df.groupby("Action")["Proceeds"].sum()
        income = income["DIVIDEND"]
    else:
        income = 0
    return realizedytd, income, fees_expenses

#YTD Performance Analytics Function
def Get_ytd_performance(df,transaction_df,History_df,income,fees_expenses,BeginningValue=13841.74,SPYbeginngingprice=681.92,accuredincome=0.0):
    BeginningValue = BeginningValue
    accuredincome = accuredincome
    EndingValue = df["PositionValue"].sum() 
    withdrawals = transaction_df.groupby("Action")["Proceeds"].sum()
    withdrawals = withdrawals["WITHDRAWAL"]
    deposits = transaction_df.groupby("Action")["Proceeds"].sum()
    deposits = deposits["DEPOSIT"]
    NetContribution = deposits - withdrawals
    InvestmentChange = (EndingValue-BeginningValue-NetContribution) 
    InvestmentG_L = (EndingValue-BeginningValue-NetContribution-income-fees_expenses)
    SPYbeginngingprice = SPYbeginngingprice
    SPYprice = yf.download("SPY")["Close"].squeeze().iloc[-1]
    tnx = yf.Ticker('^TNX')
    raw_yield = tnx.fast_info['last_price']
    try:
        risk_free = raw_yield/100
    
    except:
            risk_free = 0.04
    port = History_df["DailyPercentChange"].iloc[1:]
    spy = History_df["SPYDailyPercentChange"].iloc[1:]
    spy_variance = spy.var()
    covariance = spy.cov(port)
    beta = covariance / spy_variance
    capm = risk_free + beta * ((History_df["SPY_Cumulative_Return"].iloc[-1]) - risk_free)
    actual_return = History_df["Port_Cumulative_Return"].iloc[-1] 
    rolling_30 = (1+ History_df["DailyPercentChange"]).iloc[-30:].prod() - 1 
    spy_rolling_30 = (1 + History_df["SPYDailyPercentChange"]).iloc[-30:].prod() - 1 
    alpha_30 = rolling_30 - spy_rolling_30

    return BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, SPYbeginngingprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome, rolling_30, spy_rolling_30, alpha_30

#Benchmark Comparsion Analytics Function
def Get_Benchmark_Comparison(History_df):
    daily_returns = History_df["DailyPercentChange"].iloc[1:]
    cumulativeport = ((1 + daily_returns).prod()-1) 
    spy_daily_returns = History_df["SPYDailyPercentChange"] 
    cumulativeSPY = ((1+ spy_daily_returns).prod()-1) 
    cumulativealpha = cumulativeport - cumulativeSPY
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
    risk_free_rate = 0.043 
    daily_mean = History_df["DailyPercentChange"].iloc[1:].mean()
    annualized_mean = daily_mean * 252
    port_std = History_df["DailyPercentChange"].iloc[1:].std()
    spy_std = History_df["SPYDailyPercentChange"].iloc[1:].std() 
    sharpe_ratio = (annualized_mean - risk_free_rate) / (port_std * np.sqrt(252))
    port = History_df["DailyPercentChange"].iloc[1:]
    spy = History_df["SPYDailyPercentChange"].iloc[1:] 
    spy_variance = spy.var()
    covariance = spy.cov(port)
    beta = covariance / spy_variance  
    returns = History_df["DailyPercentChange"] 
    neg_returns = returns[returns < 0.00]
    if neg_returns.empty or len(neg_returns) < 2:
        sortino_ratio = 0
    else:
        downsidedev = neg_returns.std() * np.sqrt(252)
        sortino_ratio = (annualized_mean - risk_free_rate) /downsidedev 
    correlation = covariance /(port_std * spy_std)

    return daily_mean, port_std, sharpe_ratio, beta, sortino_ratio, correlation

#Trading Extremes Analytics Function
def Get_Trading_Extremes(History_df):
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
    filter = ~df["AssetType"].isin(["Cash","Cash Equivalent"])
    Sector_Allocation = (df[filter].groupby("Sector")["PositionValue"].sum() / df["PositionValue"].sum()).sort_values(ascending=False)
    return Sector_Allocation

#Top Holdings/Concentration Analytics Function 
def Get_Top_Holdings(df):
    filter = df["AssetType"] != "Cash"
    Top_Holdings = df[filter].nlargest(5, "PortfolioWeight")[["Ticker","PositionValue","PortfolioWeight"]]
    return Top_Holdings

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
        roe = info.get("returnOnEquity")
        beta = info.get("beta")
        dct = {"Ticker":i,"TrailingPE":trailing_pe,"ForwardPE":foward_pe,"ROE":roe,"Beta":beta}
        results.append(dct)
    results = pd.DataFrame(results)
    
    return results 
    
#Risk Flags Analytics Function 
def Get_risk_flags(df):
    portfolio_concentration = (df["PortfolioWeight"] > .10) & ~df["AssetType"].isin(["Cash","Cash Equivalent"])
    sector_concentration = (df.groupby("Sector")["PositionValue"].sum()) / df["PositionValue"].sum()
    sector_concentration = sector_concentration[sector_concentration > .35]
    severe_position_loss = df["ReturnPct"] < -.25
    if df['AssetType'].isin(['Option']).any():
        option_concentration = df[df["AssetType"] == "Option"]
        option_concentration = option_concentration["PortfolioWeight"].sum()
    else:
        option_concentration = 0.0
    return portfolio_concentration, sector_concentration, severe_position_loss, option_concentration
 
    
# =========================
# HISTORY TRACKER
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

def Save_Portfolio_History(Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct, latest_price, latest_date,road=BASE_PATH + r"\history_data.xlsx"):
    road = road
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
        percentchange = (History_df["PortfolioValue"].iloc[A] - History_df["PortfolioValue"].iloc[B] - History_df["NetFlow"].iloc[A]) / History_df["PortfolioValue"].iloc[B] 
        History_df.loc[History_df.index[A],"DailyPercentChange"] = percentchange 
    daily_return = (1 + (History_df["DailyPercentChange"])).cumprod() - 1 
    History_df["Port_Cumulative_Return"] = daily_return

    #Daily SPY Percent Change and Cumulaitve Change
    History_df["SPYDailyPercentChange"] = 0.00
    for i in range(1,len(History_df)):
        A = i
        B = i - 1 
        percentchange = (History_df["SPYCLOSE"].iloc[A] - History_df["SPYCLOSE"].iloc[B]) / History_df["SPYCLOSE"].iloc[B]   
        History_df.loc[History_df.index[A],"SPYDailyPercentChange"] = percentchange
    SPY_daily_return = (1 + (History_df["SPYDailyPercentChange"])).cumprod() - 1 
    History_df["SPY_Cumulative_Return"] = SPY_daily_return

    #ALPHA and Win/Loss Counter
    History_df["DailyAlpha"] = History_df["DailyPercentChange"] - History_df["SPYDailyPercentChange"]
    History_df["Win/LoseCounter"] = 0.00
    
    #Drawdown 
    History_df["RunningPeak"] = History_df["PortfolioValue"].cummax()
    History_df["Drawdown"] = 0.0
    Drawdown =  (History_df["PortfolioValue"] - History_df["RunningPeak"]) / History_df["RunningPeak"] 
    History_df["Drawdown"] = Drawdown
  
    return History_df

# =========================
# MPT INPUTS 
# =========================

#Create Histroical Daily Return / Covariance Matrix / Expected Return Series
def Get_MPT_Data(df): 
    equity_list = (df["AssetType"].isin(["Equity","Cash Equivalent"]))
    equity_list = df[equity_list]['Ticker'].str.strip().str.upper()
    equity_list = list(equity_list)
    start_date = "2022-01-01"
    historical_price_data = yf.download(equity_list, start=start_date)["Close"].pct_change().dropna()
    cov_matrix = historical_price_data.cov()
    expected_returns = historical_price_data.mean()
    return cov_matrix, expected_returns

#Create Weights for Equity / Cash Equivalent Holdings
def Get_MPT_Weights(df):
    equity_weights = (df["AssetType"].isin(["Equity","Cash Equivalent"]))
    equity_weights = df[equity_weights][["Ticker","PortfolioWeight"]].sort_values(by="Ticker")
    equity_weights = equity_weights.set_index("Ticker")
    total_equity_weight = equity_weights.sum()
    equity_weights = (equity_weights / total_equity_weight)
    return equity_weights

#Generate Random Weights 
def Generate_Random_Weights(equity_weights):
    random_weights = np.random.rand(len(equity_weights))
    total_random_weights = random_weights.sum()
    random_weights = (random_weights/total_random_weights)
    random_weights = pd.Series(random_weights, index=equity_weights.index)
    return random_weights

#Calcualte Expected Portfolio Return / Volatility
def Calculate_MPT_Metrics(cov_matrix,expected_returns,equity_weights):
    portfolio_return = expected_returns @ equity_weights
    annual_return = portfolio_return * 252
    portfolio_variance = equity_weights.T @ cov_matrix @ equity_weights
    portfolio_volatility = portfolio_variance ** 0.5
    annual_volatility = portfolio_volatility * (252 ** 0.5) 
    return annual_return, annual_volatility

# Create Efficent Frontier DF
def Efficent_Frontier(cov_matrix,expected_returns,equity_weights):
    random_ports = []
    for i in range(5000):
        weights = Generate_Random_Weights(equity_weights)
        return_, vol = Calculate_MPT_Metrics(cov_matrix,expected_returns,weights)
        dct = {"Return":return_,"Volatility":vol,"Weights":weights}
        random_ports.append(dct)
    df_random_ports = pd.DataFrame(random_ports)
    return df_random_ports

#Analyze Efficient Frontier 
def Analyze_Efficient_Frontier(df_random_ports):
    valid_volatility = df_random_ports['Volatility'].dropna()
    min_vol_idx = valid_volatility.idxmin()
    min_vol_port = df_random_ports.loc[min_vol_idx]
    df_random_ports["Sharpe"] = (df_random_ports["Return"] - 0.04) / df_random_ports["Volatility"]
    max_sharpe_idx = df_random_ports["Sharpe"].idxmax()
    max_sharpe_port = df_random_ports.loc[max_sharpe_idx]
    return min_vol_port, max_sharpe_port

# Using Scipy to Optimize for Max Sharpe Ratio
def Negative_Sharpe(weights, cov_matrix, expected_returns, risk_free_rate=0.04):
    annual_return, annual_volatility = Calculate_MPT_Metrics(cov_matrix,expected_returns,weights)
    sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility
    return -sharpe_ratio

# Using Scipy to Optimize for Max Sharpe Ratio
def Optimize_Max_Sharpe(cov_matrix, expected_returns,weights=(0, 0.10)):
    num_assets = len(expected_returns)
    constraints = ({"type": "eq","fun": lambda weights: np.sum(weights) - 1})
    bounds = tuple(weights for _ in range(num_assets))
    initial_guess = np.array([1 / num_assets] * num_assets)
    optimized_results = minimize(Negative_Sharpe, initial_guess, args=(cov_matrix, expected_returns), method="SLSQP", bounds=bounds, constraints=constraints) 
    optimal_weights = optimized_results.x
    optimal_return, optimal_volatility = Calculate_MPT_Metrics(cov_matrix,expected_returns,optimal_weights)
    optimal_sharpe = (optimal_return - 0.04) / optimal_volatility
    optimal_weights = pd.Series(optimal_weights, index = expected_returns.index)
    return optimal_weights, optimal_return, optimal_volatility, optimal_sharpe

#Analyze Weight Allocation 
def Analyze_Weight_Allocation(min_vol_port,max_sharpe_port,equity_weights,optimal_weights,path=BASE_PATH + r"\max_sharpe_data.xlsx"): 
    Weights_df = pd.concat([equity_weights,min_vol_port["Weights"],max_sharpe_port["Weights"]],axis=1)
    Weights_df.columns = ["Current", "MinVol", "MaxSharpe"]
    path = path
    Max_Sharpe_df = pd.read_excel(path)
    max_weights_only = max_sharpe_port["Weights"]
    new_row = pd.DataFrame(max_weights_only).T
    new_row["Return"] = max_sharpe_port["Return"]
    new_row["Volatility"] = max_sharpe_port["Volatility"]
    new_row["Sharpe"] = max_sharpe_port["Sharpe"]
    Max_Sharpe_df = pd.concat([Max_Sharpe_df,new_row],ignore_index=True) 
    Max_Sharpe_df.to_excel(path,index=False)
    max_sharpe_mean = Max_Sharpe_df.drop(columns=["Return","Volatility"]).mean()
    Weights_df["AvgMaxSharpe"] = max_sharpe_mean
    Weights_df["AvgMaxSharpe"] = Weights_df["AvgMaxSharpe"] / Weights_df["AvgMaxSharpe"].sum()
    Weights_df["Difference"] = Weights_df["AvgMaxSharpe"] - Weights_df["Current"] 
    Weights_df = pd.concat([Weights_df,optimal_weights.rename("Optimal")],axis = 1)
    Weights_df["OptimalDifference"] = Weights_df["Optimal"] - Weights_df["Current"]
    avg_return = Max_Sharpe_df["Return"].mean()
    avg_volatility = Max_Sharpe_df["Volatility"].mean()
    avg_sharpe = Max_Sharpe_df["Sharpe"].mean()
    return Weights_df, avg_volatility, avg_return, avg_sharpe


# =========================
# Portfolio Management 
# =========================

#Create Management df
def Get_Management_df(df, results):
    filter = df[df["AssetType"].isin(["Equity"])]
    equity_list = df[df["AssetType"].isin(["Equity"])]["Ticker"].tolist()
    filtered_results = results[results['Ticker'].isin(equity_list)]
    filter = pd.merge(filter,filtered_results,on='Ticker',how='inner')

    data_df = pd.DataFrame({"CurrentPrice":filter["LivePrice"],"ReturnPct":filter["ReturnPct"],"Weight":filter["PortfolioWeight"],'Beta':filter['Beta']})
    data_df.index = equity_list
    price_history = yf.download(equity_list, period ="1y")["Close"]
    dma20 = price_history.rolling(20).mean().iloc[-1]
    dma50 = price_history.rolling(50).mean().iloc[-1]
    dma200 = price_history.rolling(200).mean().iloc[-1]
    dma_df = pd.concat([dma20,dma50,dma200],axis=1)
    dma_df.columns = ["DMA20", "DMA50", "DMA200"]
    dma_df.index = equity_list
    management_df = pd.concat([data_df,dma_df],axis=1)
    return management_df, price_history

#Get Sell Conditions
def Get_Sell_Conditions(management_df, price_history):
    week_high_52 = price_history.max()
    conditions = [
    (management_df["CurrentPrice"] > management_df["DMA20"]) & 
    (management_df["DMA20"] > management_df["DMA50"]) & 
    (management_df["DMA50"] > management_df["DMA200"]),
    
    (management_df["CurrentPrice"] > management_df["DMA50"]) & 
    (management_df["DMA50"] > management_df["DMA200"]),
    
    (management_df["CurrentPrice"] < management_df["DMA200"]),

    (management_df["CurrentPrice"] < management_df["DMA50"])
    ]
    choices = ["Strong Uptrend","Healthy Uptrend", "Broken", "Weakening"]
    management_df["TrendStatus"] = np.select(conditions, choices, default="Neutral")
    management_df["DistanceFromDMA50"] = (management_df["CurrentPrice"] - management_df["DMA50"]) / management_df["DMA50"]
    management_df["DistanceFrom52WeekHigh"] = (management_df["CurrentPrice"] - week_high_52) / week_high_52 
    return management_df

#Get Risk Score
def Get_Risk_Score(management_df):
   risk_conditions = [
       (management_df["Weight"] < 0.05),
       (management_df["Weight"] < 0.10),
       (management_df["Weight"] < 0.15)
   ]
   risk_points = [0,10,20]
   risk_labels = ["Normal", "Elevated", "Oversized"]
   management_df["RiskConcentration"] = np.select(risk_conditions,risk_points, default=30)
   management_df["RiskConcentrationLabel"] = np.select(risk_conditions,risk_labels, default="Critical Concentration")

   beta_conditions = [
       (management_df['Beta'] < 0.75),
       (management_df['Beta'] < 1.00),
       (management_df['Beta'] < 1.25),
       (management_df['Beta'] < 1.50),
       (management_df['Beta'] < 2.00),
   ]
   beta_points = [0,8,15,22,29]
   management_df['BetaRisk'] = np.select(beta_conditions,beta_points, default=15)

   trend_status_conditions = [
       (management_df["TrendStatus"] == "Strong Uptrend"),
       (management_df["TrendStatus"] == "Healthy Uptrend"),
       (management_df["TrendStatus"] == "Neutral"),
       (management_df["TrendStatus"] == "Weakening")
   ]
   trend_points = [0,8,15,22]
   management_df["TrendRisk"] = np.select(trend_status_conditions, trend_points, default=30)

   distance_from_52_conditions = [
       (management_df["DistanceFrom52WeekHigh"] < -0.30),
       (management_df["DistanceFrom52WeekHigh"] < -0.15),
       (management_df["DistanceFrom52WeekHigh"] < -0.05)
   ]
   distance_52_points = [25,17,8]
   management_df["DrawdownRisk"] = np.select(distance_from_52_conditions, distance_52_points, default=0)

   extension_risk_conditions = [
       (management_df["DistanceFromDMA50"] > .35),
       (management_df["DistanceFromDMA50"] > .20),
       (management_df["DistanceFromDMA50"] > 0.0)
   ]
   extension_risk_points = [15,8,10]
   management_df["ExtensionRisk"] = np.select(extension_risk_conditions,extension_risk_points,default=0)
   management_df["RiskScore"] = management_df["RiskConcentration"] + management_df['BetaRisk'] + management_df["TrendRisk"] + management_df["DrawdownRisk"] + management_df["ExtensionRisk"]

   risk_score_category = [
         (management_df["RiskScore"] <= 35),
         (management_df["RiskScore"] <= 70),
         (management_df["RiskScore"] <= 95)
   ]
   risk_score_labels = ["Low Risk","Moderate Risk","High Risk"]
   management_df["RiskCategory"] = np.select(risk_score_category, risk_score_labels, default="Critical Risk")

   sell_decision_conditions = [
       (management_df["DistanceFromDMA50"] > .35) & (management_df["TrendStatus"].isin(["Strong Uptrend","Healthy Uptrend"])),
       (management_df["RiskCategory"].isin(["Low Risk","Moderate Risk"]))  & (management_df["TrendStatus"].isin(["Strong Uptrend","Healthy Uptrend"])),
       (management_df["RiskCategory"].isin(["High Risk","Critical Risk"])) & (management_df["TrendStatus"].isin(["Strong Uptrend","Healthy Uptrend"])),
       (management_df["RiskCategory"].isin(["Low Risk", "Moderate Risk"])) & (management_df["TrendStatus"] == "Neutral"),
       (management_df["RiskCategory"].isin(["High Risk","Critical Risk"])) & (management_df["TrendStatus"].isin(["Neutral","Weakening"])),
       (management_df["RiskCategory"].isin(["Moderate Risk","High Risk"])) & (management_df["TrendStatus"] == "Broken")
   ]
   sell_decision_labels = ["TRIM","HOLD","TRIM","MONITOR","REVIEW","DE-RISK"]
   management_df["SellDecision"] = np.select(sell_decision_conditions, sell_decision_labels, default="EXIT CANDIDATE")

   return management_df
       
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
    print(f"{'Total Portfolio Value:':<24} {f'${df["PositionValue"].sum():,.2f}':>10}")
    print(f"{'P/L Open:':<24} {f'${df["UnrealizedP&L"].sum():,.2f}':>10}")

#YTD Performance Output Function
def ytd_performance_Output(BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, income, fees_expenses, InvestmentG_L, accuredincome):
    print("YTD Performance\n" + '-' * 25)
    print(f"{'Beginning Value:':<22} {f'${BeginningValue:,.2f}':>12}")
    print(f"{'   Contributions':<24} {f'+${deposits:,.2F}':>10}")
    print(f"{'   Withdrawals':<24} {f'-${withdrawals:,.2F}':>10}")
    print(f"{'Net Contributions:':<22} {f'${NetContribution:,.2f}':>12}")
    if InvestmentG_L > 0:
        print(f"{'   Investment G/L':<24} {f'+${InvestmentG_L:,.2f}':>10}")
    else:
        print(f"{'   Investment G/L':<24} {f'{InvestmentG_L:,.2f}':>10}")
    print(f"{'   Income':<24} {f'+${income:,.2f}':>10}")
    print(f"{'   Fees & Expenses':<24} {f'${fees_expenses:,.2f}':>10}")
    print(f"{'Investment Change:':<22} {f'${InvestmentChange:,.2f}':>12}")
    print(f"{'   Market Value':<24} {f'${EndingValue:,.2f}':>10}")
    print(f"{'   Accured Income':<24} {f'${accuredincome}':>10}")
    print(f"{'Ending Value:':<22} {f'${EndingValue + accuredincome:,.2f}':>12}")

#Performance Analytics Output Function 
def Perfromance_Analytics_Output(BeginningValue, InvestmentChange, SPYbeginningprice, SPYprice, capm, actual_return, rolling_30, spy_rolling_30, alpha_30):
    print("Perfromance Analytics\n" + "-" * 25)
    print(f"{"Portfolio Return (TWR):":<27} {f'{(actual_return) * 100:.2f}%':>7}")
    print(f"{'Simple Return YTD:':<27} {InvestmentChange/BeginningValue * 100:>6.2f}%")
    print(f"{'Benchmark (SPY YTD):':<26} {(SPYprice - SPYbeginningprice) / SPYbeginningprice * 100:>7.2f}%")
    print(f"{'Alpha (TWR):':<24} {f'{(actual_return * 100) - ((SPYprice - SPYbeginningprice) / SPYbeginningprice) * 100:.2f}%':>10}")
    print()
    print(f"{'30D Portfolio Return:':<24} {f'{rolling_30 * 100:.2f}%':>10}")
    print(f"{'30D SPY Return:':<24} {f'{spy_rolling_30 * 100:.2f}%':>10}")
    print(f"{'30D Alpha:':<24} {f'{alpha_30 * 100:.2f}%':>10}")
    print()
    print(f"{'CAPM Expected Return:':<27} {f'{capm * 100:.2f}%':>7}")
    print(f"{'Alpha (CAPM):':<24} {f'{(actual_return - capm) * 100:.2f}%':>10}")

#Return Attribution Output Function
def return_attribution_Output(df,realizedytd,income,fees_expenses,accuredincome):
    print("P&L Attribution\n" +  "-" * 25)
    filter = (df[df["AssetType"] != "Cash"])
    total_return = fees_expenses + realizedytd + income + accuredincome + filter["UnrealizedP&L"].sum()
    print(f"{'Unrealized:':<24} {f'${df["UnrealizedP&L"].sum():,.2f}':>10} {f'(+{(df["UnrealizedP&L"].sum() / total_return)* 100:.0f}%)':>10}")
    print(f"{'Realized:':<25}{f'${realizedytd:,.2f}':>10} {f'({(realizedytd / total_return) * 100:.0f}%)':>10}")
    print(f"{'Income:':<25}{f'${income:.2f}':>10} {f'(+{(income/total_return) * 100:.0f}%)':>10}")
    print(f"{'Accured Income:':<29} {f'${accuredincome:.2f}':>5} {f'(+{(accuredincome/total_return) * 100:.0f}%)':>10}")
    print(f"{'Fees & Expenses:':<28} {f'${fees_expenses:.2f}':>6} {f'({(fees_expenses/total_return) * 100:.0f}%)':>10}")
    print("-" * 25)
    print(f"{'Total:':<25} {f'${total_return:,.2f}':>9} {f'({(total_return/total_return)* 100:.0f}%)':>10}")

#Bench Mark Comparison Output Function
def Benchmark_Comparison_Output(cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays,History_df):
    print("Daily Performance vs SPY\n" + "-" * 38)
    print(f"{'Date':<10} {'Port %':>9} {'SPY %':>14} {'Alpha':>14}\n" + "-" * 48)
    for index,row in History_df[["DailyPercentChange","SPYDailyPercentChange","DailyAlpha"]].iloc[-20:].iterrows():
        print(f"{str(index):<10} {row["DailyPercentChange"] * 100:>8.2f}% {row["SPYDailyPercentChange"] * 100:>13.2f}% {row["DailyAlpha"] * 100:>13.2f}%" )
    print("-" * 48)
    print(f"Cumulative:{cumulativeport * 100:>8.2f}% {cumulativeSPY * 100:>13.2f}% {cumulativealpha * 100:>13.2f}%") 
    print(f"Win Rate vs SPY: {WinLosepercent * 100:.2f}% ({win}/{TotalDays})") 

#Risk Metrics Output Function
def Risk_Metrics_Output(daily_mean,port_std,sharpe_ratio,beta,History_df,sortino_ratio,correlation):
    print("Risk & Return Analytics\n" + '-' * 25)
    print(f"{'Daily Mean:':<19} {daily_mean * 100:.2f}%")
    print(f"{'Daily Volatility:':<18} ±{port_std * 100:.2f}%")
    print(f"{'Correlation:':<20}{correlation:>4.2f}")
    print(f"{'Sharpe Ratio:':<19} {f'{sharpe_ratio:.2f}':>5}")
    print(f"{'Sortino Ratio:':<20}{f'{sortino_ratio:.2f}':>5}")
    print(f"{'Beta:':<19} {beta:>5.2f}")
    print(f"{'Current Drawdown:':<15} {f'{(History_df["Drawdown"].iloc[-1] * 100):.2f}%':>7}")
    print(f"{'Max Drawdown:':<16} {f'{(History_df["Drawdown"].min() * 100):.2f}%':>8}")
    Drawdown_Duration = 0
    for i in History_df["Drawdown"][::-1]:    
        if i < 0.0:
            Drawdown_Duration += 1 
        else:
            break
    print(f"{'Drawdown Duration:':<15} {f'{Drawdown_Duration}':>5}d")

#Trading Extremes Output Function
def Trading_Extremes_Output(Best_day, best_day, Worst_day, worst_day):
    print("Trading Extremes\n" + "-" *25)
    print("Best Day:")
    print(f"{str(Best_day):<10} | +{best_day["DailyPercentChange"] * 100:<4.2f}% | +${best_day["P/L Day"]:<8}")
    print() 
    print("Worst Day:")
    print(f"{str(Worst_day):<10} | {worst_day["DailyPercentChange"] * 100:<4.2f}% | ${worst_day["P/L Day"]:<8}")
    
#Total Expsoure by AssetType Output Function 
def Asset_Exposure_Output(Asset_Exposure):  
    print("Portfolio Asset Exposure\n"+ "-" * 25)
    print(f"{'Class':<10}{'Weight':>25}")
    print("-" * 38)
    print(f"Equity Allocation: {Asset_Exposure["Equity"]*100:>15.2f}%")
    if Asset_Exposure.index.isin(['Option']).any():
        print(f"Option Allocation: {Asset_Exposure["Option"]*100:>15.2f}%") 
    if Asset_Exposure.index.isin(['Cash Equivalent']).any():
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
def Top_Holdings_Output(Top_Holdings):
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

#Efficient Frontier Output Function
def Efficient_Frontier_Output(Weights_df, avg_volatility, avg_return, avg_sharpe, daily_mean, port_std, sharpe_ratio, optimal_return, optimal_volatility, optimal_sharpe):
    RED = '\033[91m'
    GREEN = '\033[92m'
    RESET = '\033[0m'
    print("Efficient Frontier\n" + "-" * 25)
    print(f"{"Ticker":<9} {"Current":<10} {"Opt Sharpe":<12} {"Avg Front":<12} {"Opt Diff":<11} {"Sim Diff"}")
    print("-" * 68)
    for row in Weights_df.itertuples():
        diff_color = RED if row.Difference < 0 else GREEN if row.Difference > 0 else RESET
        diff_color_opt = RED if row.OptimalDifference < 0 else GREEN if row.OptimalDifference > 0 else RESET
        print(f"{row.Index:<8} {f'{row.Current * 100:.2f}%':>7} {f'{row.Optimal * 100:.2f}%':>12} {f'{row.AvgMaxSharpe * 100:.2f}%':>11} {diff_color_opt}{row.OptimalDifference * 100:>10.2f}%{RESET} {diff_color}{row.Difference * 100:>10.2f}%{RESET}")
    print()
    print("Efficient Frontier Summary\n" + "-" * 38)
    print(f"{'Avg Max Sharpe Return:':<24} {f'{avg_return * 100:.2f}%':>10}")
    print(f"{'Avg Max Sharpe Volatility:':<23} {f'{avg_volatility * 100:.2f}%':>8}")
    print(f"{'Avg Max Sharpe Ratio:':<24} {f'{avg_sharpe:.2f}':>10}")
    print()
    print(f"{'Optimal Return:':<24} {f'{optimal_return * 100:.2f}%':>10}")
    print(f"{'Optimal Volatility:':<26} {f'{optimal_volatility * 100:.2f}%':>8}")
    print(f"{'Optimal Sharpe Ratio:':<24} {f'{optimal_sharpe:.2f}':>10}")
    print()
    print(f"{'Exp. Portfolio Return:':<27} {f'{(daily_mean * 252) * 100:.2f}%':>7}")
    print(f"{'Exp. Portfolio Volatility:':<26} {f'{(port_std * np.sqrt(252)) * 100:.2f}%':>8}")
    print(f"{'Exp. Portfolio Sharpe:':<26} {f'{sharpe_ratio:.2f}':>8}")

#Invesment Fundementals Output Function 
def Investment_Fundementals_Ouput(results):
    print("Investment Fundementals\n" + "-" * 25)
    print(f"{'Ticker':<9}{'PE(T)':<9}{'PE(F)':<10}{'ROE':<9}{'Beta':<9}")
    print("-" * 48)
    for row in results.itertuples():
        print(f"{row.Ticker:<6}{row.TrailingPE:>8.2f}{row.ForwardPE:>9.2f}{f'{row.ROE * 100:.2f}%':>10}{row.Beta:>8.2f}")

#Portfolio Management Output Function
def Portfolio_Management_Output(management_df):
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = "\033[93m"
    ORANGE = "\033[38;5;208m"
    CYAN = "\033[96m"
    RESET = '\033[0m'
    print("Portfolio Management System\n" + "-" * 27)
    print(f"{'Ticker':<2} {'Weight':>10} {'Beta':>10} {'Return%':>11} {'Trend Status':>16} {'DistFromDMA50':>17} {'DistFrom52WkHigh':>20} {'RiskScore':>13} {'RiskCategory':>16} {'SellDecision':>16}")
    print("-" * 133)
    for row in management_df.itertuples():
         diff_color = GREEN if row.TrendStatus in ["Strong Uptrend","Healthy Uptrend"] else YELLOW if row.TrendStatus == "Neutral" else ORANGE if row.TrendStatus == "Weakening" else RED if row.TrendStatus == "Broken" else RESET
         diff_color_risk = GREEN if row.RiskCategory == "Low Risk" else YELLOW if row.RiskCategory == "Moderate Risk" else ORANGE if row.RiskCategory == "High Risk" else RED if row.RiskCategory == "Critical Risk" else RESET
         diff_color_sell = GREEN if row.SellDecision == "HOLD" else YELLOW if row.SellDecision == "MONITOR" else CYAN if row.SellDecision == "TRIM" else ORANGE if row.SellDecision == "REVIEW" else RED if row.SellDecision in ["DE-RISK","EXIT CANDIDATE"] else RESET
         print(f"{row.Index:<7} {f'{row.Weight * 100:.2f}%':>9} {row.Beta:>10} {f'{row.ReturnPct * 100:.2f}%':>11} {diff_color}{row.TrendStatus:>17}{RESET} {f'{row.DistanceFromDMA50 * 100:.2f}%':>13} \
        {f'{row.DistanceFrom52WeekHigh * 100:.2f}%':>10} {row.RiskScore:>14} {diff_color_risk}{row.RiskCategory:>21}{RESET} {diff_color_sell}{row.SellDecision:>13}{RESET}")

#Risk Flags Output Function 
def risk_flags_Output(df,portfolio_concentration,sector_concentration,severe_position_loss,option_concentration):
    print("Risk Flags\n" + "-" * 25)
    has_warnings = portfolio_concentration.any() or sector_concentration.any() or severe_position_loss.any() or option_concentration > .10
    if portfolio_concentration.any():
        for index,row in df[portfolio_concentration][["Ticker","PortfolioWeight"]].iterrows():
            print(f"🚨 {row["Ticker"]} at {row["PortfolioWeight"] * 100:.2f}% of portfolio")
    if sector_concentration.any():
        for index,row in sector_concentration.items():
            print(f"🚨 {index}at {row * 100:.2f}% (high concentration) ")
    if severe_position_loss.any():
        for index,row in df[severe_position_loss][["Ticker","ReturnPct"]].iterrows():
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

# =========================
# Chart Functions
# =========================

#Section Allocation Breakdown
def Show_Sector_Allocation(df):
    def handle_close(event):
        print("Sector Allocation closed. Press Enter to return to dashboard.")
    fig, ax = plt.subplots(figsize=(10,6))
    fig.set_facecolor('White')
    ax.grid(True, color ='gray')
    sector_allocation = df.groupby("Sector")["PositionValue"].sum() / df["PositionValue"].sum()
    sector_allocation = sector_allocation.sort_values(ascending=True)
    ax.pie(sector_allocation, labels=sector_allocation.index, autopct='%1.2f%%')
    ax.set_title("Sector Allocation")
    fig.canvas.mpl_connect('close_event', handle_close)
    plt.tight_layout()
    plt.show()

#Portfolio Vs. SPY
def Show_Portfoio_VS_SPY(History_df):
    def handle_close(event):
        print("Portfolio vs SPY closed. Press Enter to return to dashboard.")
    fig, ax = plt.subplots(figsize=(10,6))
    fig.set_facecolor('White')
    ax.grid(True, color ='gray')
    ax.plot(History_df.index, History_df["Port_Cumulative_Return"] * 100)
    ax.plot(History_df.index, History_df["SPY_Cumulative_Return"] * 100)
    ax.set_title("Portfolio vs SPY Performance")
    ax.set_ylabel("Return (%)")
    ax.set_xlabel("Date")
    ax.legend(["Portfolio","SPY"])
    fig.canvas.mpl_connect('close_event', handle_close)
    plt.tight_layout()
    plt.show()

#Efficient Frontier
def Show_Efficient_Frontier(df_random_ports,min_vol_port,max_sharpe_port,annual_volatility,annual_return):
    def handle_close(event):
        print("Efficient Frontier closed. Press Enter to return to dashboard.")
    fig, ax = plt.subplots(figsize=(10,6))
    fig.set_facecolor('White')
    ax.grid(True, color ='gray')
    ax.scatter(df_random_ports["Volatility"],df_random_ports["Return"], alpha=0.3, label="Random Portfolios") 
    ax.scatter(min_vol_port["Volatility"], min_vol_port["Return"],marker="o",s=100,label="Min Vol")
    ax.scatter(max_sharpe_port["Volatility"], max_sharpe_port["Return"],marker="o",s=100, label="Max Sharpe")
    ax.scatter(annual_volatility,annual_return, marker="o", s=100, c='black',label="My Portfolio")
    ax.set_title("Efficient Frontier")
    ax.set_xlabel("Volatility (%)")
    ax.set_ylabel("Return (%)")
    ax.legend()
    fig.canvas.mpl_connect('close_event', handle_close)
    plt.tight_layout()
    plt.show()

#Return Distriubtion
def Show_Return_Distriubtion(History_df):
    def handle_close(event):
        print("Daily Return Distribution closed. Press Enter to return to dashboard.")
    fig, ax = plt.subplots(figsize=(10,6))
    fig.set_facecolor('White')
    ax.grid(True, color ='gray')
    returns = History_df["DailyPercentChange"].iloc[1:]
    mean = returns.mean()
    std = returns.std()
    x = np.linspace(returns.min(), returns.max(), 100)
    y = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean) / std) ** 2)
    ax.hist(returns, bins=20, density=True, alpha=0.4)
    ax.set_title("Daily Return Distribution")
    ax.set_xlabel("Returns")
    ax.set_ylabel("Density")
    ax.plot(x,y, linewidth=3)
    ax.axvline(mean, color='black',linewidth=3,label='Mean',alpha=0.7)    
    ax.axvline(mean + std,color='red',linestyle='--')
    ax.axvline(mean - std,color='red',linestyle='--',alpha=0.7)
    ax.grid(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend()
    fig.canvas.mpl_connect('close_event', handle_close)
    plt.tight_layout()
    plt.show()

def Run_Chart_Dashboard(df,History_df,df_random_ports,min_vol_port,max_sharpe_port,annual_volatility,annual_return,actual_return,sharpe_ratio,beta,WinLosepercent):
    while True:
        RED = '\033[91m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        HEADER = '\033[1;100m'
        RESET = '\033[0m'
        print(f"{HEADER}PORTFOLIO DASHBOARD{RESET}\n" + "-" * 25)
        print(f"{'Value:'} {f'${df["PositionValue"].sum():,.2f}':>12}")
        if actual_return > 0.0:
            print(f"{'TWR:'} {GREEN}{f'{actual_return * 100:.2f}%':>14}{RESET}")
        else:
            print(f"{'TWR:'} {f'{actual_return * 100:.2f}%':>14}")
        print(f"{'Sharpe:'} {f'{sharpe_ratio:.2f}':>11}")
        print(f"{'Beta:'} {f'{beta:.2f}':>13}")
        if History_df["Drawdown"].min() == 0.0:
            print(f"{'Max DD:'} {f'{(History_df["Drawdown"].min() * 100):.2f}%':>11}")
        else: 
            print(f"{'Max DD:'} {RED}{f'{(History_df["Drawdown"].min() * 100):.2f}%':>11}{RESET}")
        if WinLosepercent > .50:
            print(f"{'Win Rate:'} {GREEN}{f'{WinLosepercent * 100:.2f}%':>9}{RESET}")
        else:
             print(f"{'Win Rate:'} {RED}{f'{WinLosepercent * 100:.2f}%':>9}{RESET}")
        print()
        print(f"{HEADER}COMMANDS{RESET}")
        print("-" * 25)
        print(f"{'sector':<10} {'Sector Allocation'}")
        print(f"{'spy':<10} {'Portfolio vs SPY'}")
        print(f"{'front':<10} {'Efficient Frontier'}")
        print(f"{'dist':<10} {'Daily Return Distriubtion'}")
        print(f"{'exit':<10} {'Close dashboard'}")
        print()
        selection = input("Command: ")
        if selection == "0" or selection == "exit":
            print("Closing Dashboard")
            break
        if selection == "1" or selection == "sector":
            print("Opening Sector Allocation...")
            Show_Sector_Allocation(df)
        elif selection == "2" or selection == "spy":
            print("Opening Portfolio vs SPY...")
            Show_Portfoio_VS_SPY(History_df)
        elif selection == "3" or selection == "frontier":
           print("Opening Efficient Frontier...")
           Show_Efficient_Frontier(df_random_ports,min_vol_port,max_sharpe_port,annual_volatility,annual_return)
        elif selection == "4" or selection == "dist":
            print("Opening Daily Return Distribution...")
            Show_Return_Distriubtion(History_df)
        else:
            break
        input()


# =========================
# EXECUTION LAYER
# =========================



def Execution(df,transaction_df,arbitrage_df,arbitrage_transaction_df,portfolio_type='current'):
    df = Pricing(df)
    df = Calculations(df)

    arbitrage_df = Pricing(arbitrage_df)
    arbitrage_df = Calculations(arbitrage_df)


    if portfolio_type == 'current':
        Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct = Get_Portfolio_History(df)
        latest_price, latest_date = Get_Today_SPY_Close()
        History_df = Save_Portfolio_History(Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct, latest_price, latest_date,road=BASE_PATH + r"\history_data.xlsx")
        History_df = Upgrade_History_df(History_df,transaction_df)
        results = Get_Investment_Fundementals(df)

        Total_Positions,Equities, Options, Sectors, Mean_Size, Largest_Position_Size = Get_position_summary(df)
        realizedytd,income,fees_expenses = Get_pnl_components(transaction_df)
        BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, SPYbeginningprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome, rolling_30, spy_rolling_30, alpha_30 = Get_ytd_performance(df,transaction_df,History_df,income,fees_expenses,BeginningValue=13841.74,SPYbeginngingprice=681.92,accuredincome=0.0)
        cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays = Get_Benchmark_Comparison(History_df)
        daily_mean, port_std, sharpe_ratio, beta, sortino_ratio,correlation =  Get_Risk_Metrics(History_df)
        Best_day, best_day, Worst_day, worst_day = Get_Trading_Extremes(History_df)
        Asset_Exposure = Get_Asset_Exposure(df)
        Sector_Allocation = Get_Sector_Allocation(df)
        Top_Holdings = Get_Top_Holdings(df)
        top_contributors,top_detractors, = Get_Top_Movers(df)
        portfolio_concentration,sector_concentration,severe_position_loss,option_concentration = Get_risk_flags(df) 
        cov_matrix, expected_returns = Get_MPT_Data(df)
        equity_weights = Get_MPT_Weights(df) 
        annual_return, annual_volatility = Calculate_MPT_Metrics(cov_matrix,expected_returns,equity_weights)
        df_random_ports = Efficent_Frontier(cov_matrix,expected_returns,equity_weights)
        min_vol_port, max_sharpe_port = Analyze_Efficient_Frontier(df_random_ports)
        optimal_weights, optimal_return, optimal_volatility, optimal_sharpe = Optimize_Max_Sharpe(cov_matrix, expected_returns,weights=(0, 0.10))
        Weights_df, avg_volatility, avg_return, avg_sharpe = Analyze_Weight_Allocation(min_vol_port,max_sharpe_port,equity_weights, optimal_weights,path=BASE_PATH + r"\max_sharpe_data.xlsx") 
        management_df, price_history = Get_Management_df(df, results)
        management_df = Get_Sell_Conditions(management_df, price_history)
        management_df = Get_Risk_Score(management_df)

        position_summary_Output(Total_Positions,Equities, Options, Sectors, Mean_Size, Largest_Position_Size)
        print()
        PortfolioSummary(df)
        print()
        ytd_performance_Output(BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, income, fees_expenses, InvestmentG_L, accuredincome)
        print()
        Perfromance_Analytics_Output(BeginningValue, InvestmentChange, SPYbeginningprice, SPYprice, capm, actual_return, rolling_30, spy_rolling_30, alpha_30)
        print()
        return_attribution_Output(df,realizedytd,income,fees_expenses,accuredincome)
        print()
        Benchmark_Comparison_Output(cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays,History_df)
        print()
        Risk_Metrics_Output(daily_mean,port_std,sharpe_ratio,beta,History_df,sortino_ratio,correlation)
        print() 
        Trading_Extremes_Output(Best_day, best_day, Worst_day, worst_day)
        print()
        Asset_Exposure_Output(Asset_Exposure)
        print()
        Sector_Allocation_Output(Sector_Allocation)
        print()
        Top_Holdings_Output(Top_Holdings)
        print()
        Top_Movers_Output(top_contributors,top_detractors)
        print()
        Efficient_Frontier_Output(Weights_df, avg_volatility, avg_return, avg_sharpe, daily_mean, port_std, sharpe_ratio, optimal_return, optimal_volatility, optimal_sharpe)
        print()
        Investment_Fundementals_Ouput(results)
        print()
        Portfolio_Management_Output(management_df)
        print()
        risk_flags_Output(df,portfolio_concentration,sector_concentration,severe_position_loss,option_concentration)
        print()
        Missing_Live_Prices(df)
        print()
        Optimize_Max_Sharpe(cov_matrix, expected_returns)
        # Run_Chart_Dashboard(df,History_df,df_random_ports,min_vol_port,max_sharpe_port,annual_volatility,annual_return,actual_return,sharpe_ratio,beta,WinLosepercent)

    else:
        Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct = Get_Portfolio_History(arbitrage_df)
        latest_price, latest_date = Get_Today_SPY_Close()
        History_df = Save_Portfolio_History(Today, TotalPortfolioValue, TotalUnrealizedPL, PortfolioReturnPct, latest_price, latest_date,road=BASE_PATH + r"\abitrage_history_data.xlsx")
        History_df = Upgrade_History_df(History_df,arbitrage_transaction_df)
        results = Get_Investment_Fundementals(arbitrage_df)

        Beginning_date = History_df.index[0]
        BeginningValue = History_df.loc[Beginning_date,'PortfolioValue']
        SPYbeginningprice = History_df.loc[Beginning_date,'SPYCLOSE']

        Total_Positions,Equities, Options, Sectors, Mean_Size, Largest_Position_Size = Get_position_summary(arbitrage_df)
        realizedytd,income,fees_expenses = Get_pnl_components(arbitrage_transaction_df)
        BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, SPYbeginningprice, SPYprice, capm, actual_return, InvestmentG_L, accuredincome, rolling_30, spy_rolling_30, alpha_30 = Get_ytd_performance(arbitrage_df,arbitrage_transaction_df,History_df,income,fees_expenses,BeginningValue=BeginningValue,SPYbeginngingprice=SPYbeginningprice,accuredincome=0.0)
        cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays = Get_Benchmark_Comparison(History_df)
        daily_mean, port_std, sharpe_ratio, beta, sortino_ratio,correlation =  Get_Risk_Metrics(History_df)
        Best_day, best_day, Worst_day, worst_day = Get_Trading_Extremes(History_df)
        Asset_Exposure = Get_Asset_Exposure(arbitrage_df)
        Sector_Allocation = Get_Sector_Allocation(arbitrage_df)
        Top_Holdings = Get_Top_Holdings(arbitrage_df)
        top_contributors,top_detractors, = Get_Top_Movers(arbitrage_df)
        portfolio_concentration,sector_concentration,severe_position_loss,option_concentration = Get_risk_flags(arbitrage_df) 

        cov_matrix, expected_returns = Get_MPT_Data(arbitrage_df)
        equity_weights = Get_MPT_Weights(arbitrage_df) 
        annual_return, annual_volatility = Calculate_MPT_Metrics(cov_matrix,expected_returns,equity_weights)
        df_random_ports = Efficent_Frontier(cov_matrix,expected_returns,equity_weights)
        min_vol_port, max_sharpe_port = Analyze_Efficient_Frontier(df_random_ports)
        optimal_weights, optimal_return, optimal_volatility, optimal_sharpe = Optimize_Max_Sharpe(cov_matrix, expected_returns,weights=(0, 0.40))
        Weights_df, avg_volatility, avg_return, avg_sharpe = Analyze_Weight_Allocation(min_vol_port,max_sharpe_port,equity_weights, optimal_weights,path=BASE_PATH + r"\arbitrage_max_sharpe_data.xlsx") 
        management_df, price_history = Get_Management_df(arbitrage_df, results)
        management_df = Get_Sell_Conditions(management_df, price_history)
        management_df = Get_Risk_Score(management_df)

        position_summary_Output(Total_Positions,Equities, Options, Sectors, Mean_Size, Largest_Position_Size)
        print()
        PortfolioSummary(arbitrage_df)
        print()
        ytd_performance_Output(BeginningValue, EndingValue, withdrawals, deposits, NetContribution, InvestmentChange, income, fees_expenses, InvestmentG_L, accuredincome)
        print()
        Perfromance_Analytics_Output(BeginningValue, InvestmentChange, SPYbeginningprice, SPYprice, capm, actual_return, rolling_30, spy_rolling_30, alpha_30)
        print()
        return_attribution_Output(arbitrage_df,realizedytd,income,fees_expenses,accuredincome)
        print()
        Benchmark_Comparison_Output(cumulativealpha,cumulativeport,cumulativeSPY,win,WinLosepercent,TotalDays,History_df)
        print()
        Risk_Metrics_Output(daily_mean,port_std,sharpe_ratio,beta,History_df,sortino_ratio,correlation)
        print() 
        Trading_Extremes_Output(Best_day, best_day, Worst_day, worst_day)
        print()
        Asset_Exposure_Output(Asset_Exposure)
        print()
        Sector_Allocation_Output(Sector_Allocation)
        print()
        Top_Holdings_Output(Top_Holdings)
        print()
        Top_Movers_Output(top_contributors,top_detractors)
        print()
        Efficient_Frontier_Output(Weights_df, avg_volatility, avg_return, avg_sharpe, daily_mean, port_std, sharpe_ratio, optimal_return, optimal_volatility, optimal_sharpe)
        print()
        Investment_Fundementals_Ouput(results)
        print()
        Portfolio_Management_Output(management_df)
        print()
        risk_flags_Output(arbitrage_df,portfolio_concentration,sector_concentration,severe_position_loss,option_concentration)
        print()
        Missing_Live_Prices(arbitrage_df)
        print()
        Optimize_Max_Sharpe(cov_matrix, expected_returns)
        # Run_Chart_Dashboard(arbitrage_df,History_df,df_random_ports,min_vol_port,max_sharpe_port,annual_volatility,annual_return,actual_return,sharpe_ratio,beta,WinLosepercent)
        





Execution(df,transaction_df,arbitrage_df,arbitrage_transaction_df)





  




