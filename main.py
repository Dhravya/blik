from fastapi import FastAPI
from dotenv import load_dotenv
from os import environ as env
from datetime import datetime, timedelta
import mindsdb_sdk
import cohere
import uvicorn
from cachetools import TTLCache


load_dotenv()

minds_db_connected = False
cache = TTLCache(maxsize=128, ttl=86400)

server = mindsdb_sdk.connect(
    login="dhravyashah@gmail.com",
    password=env.get("MINDSDB_PASSWORD") if not minds_db_connected else "",
)
minds_db_connected = True
print("Connected to MindsDB")
model = server.models.get(name="crypto_predictor_new")


app = FastAPI()
co = cohere.Client(env.get("COHERE_API_KEY"))

crypto_name_to_code = {
    "Bitcoin": "BTC",
    "Litecoin": "LTC",
    "XRP": "XRP",
    "Dogecoin": "DOGE",
    "Monero": "XMR",
    "Stellar": "XLM",
    "Tether": "USDT",
    "Ethereum": "ETH",
    "Ethereum Classic": "ETC",
    "Maker": "MKR",
    "Basic Attention Token": "BAT",
    "EOS": "EOS",
    "Bitcoin Cash": "BCH",
    "BNB": "BNB",
    "TRON": "TRX",
    "Decentraland": "MANA",
    "Chainlink": "LINK",
    "Cardano": "ADA",
    "Filecoin": "FIL",
    "Theta Network": "THETA",
    "Huobi Token": "HT",
    "Ravencoin": "RVN",
    "Tezos": "XTZ",
    "VeChain": "VET",
    "Quant": "QNT",
    "USD Coin": "USDC",
    "Cronos": "CRO",
    "Wrapped Bitcoin": "WBTC",
    "Cosmos": "ATOM",
    "Polygon": "MATIC",
    "OKB": "OKB",
    "UNUS SED LEO": "LEO",
    "Algorand": "ALGO",
    "Chiliz": "CHZ",
    "THORChain": "RUNE",
    "Terra Classic": "LUNA",
    "FTX Token": "FTT",
    "Hedera": "HBAR",
    "Binance USD": "BUSD",
    "Dai": "DAI",
    "Solana": "SOL",
    "Avalanche": "AVAX",
    "Shiba Inu": "SHIB",
    "The Sandbox": "SAND",
    "Polkadot": "DOT",
    "Elrond": "EGLD",
    "Uniswap": "UNI",
    "Aave": "AAVE",
    "NEAR Protocol": "NEAR",
    "Flow": "FLOW",
    "Internet Computer": "ICP",
    "Casper": "CSPR",
    "Toncoin": "TON",
    "Chain": "CHN",
    "ApeCoin": "APE",
    "Aptos": "APT",
    # ... you can add more mappings here if necessary
}


def get_crypto_code(name):
    """
    Return the code for a given cryptocurrency name.

    :param name: The full name of the cryptocurrency.
    :return: The code/symbol of the cryptocurrency or None if not found.
    """
    return crypto_name_to_code.get(name)


@app.get("/get_top")
async def get_top():
    if "cached_response" not in cache:
        response = server.query(
            f"SELECT Pred.close, Pred.date, Pred.crypto_name FROM mindsdb.crypto_predictor_new as Pred JOIN files.crypto_prices as Train WHERE Train.date > LATEST"
        ).fetch()

        # Take an average of the rate of growth of each crypto
        fastest_growing = {}
        for row, column in response.iterrows():
            # find growth rate and add to dict with key as crypto name and value as growth rate, where crypto_name can be found multiple times, take an average
            if column["crypto_name"] not in fastest_growing:
                fastest_growing[column["crypto_name"]] = column["close"]
            else:
                fastest_growing[column["crypto_name"]] = (
                    fastest_growing[column["crypto_name"]] + column["close"]
                ) / 2

        fastest_growing = sorted(
            fastest_growing.items(), key=lambda x: x[1], reverse=True
        )

        final_response = []

        for crypto in fastest_growing:
            code = get_crypto_code(crypto[0])
            url = f"https://raw.githubusercontent.com/Pymmdrza/Cryptocurrency_Logos/mainx/PNG/{code.lower() if code else 'btc'}.png"
            final_response.append(
                {
                    "crypto_name": crypto[0],
                    "crypto_code": code,
                    "img_url": url,
                    "growth_rate": crypto[1],
                    "values": [
                        {
                            "date": column["date"],
                            "close": column["close"],
                        }
                        for row, column in response.iterrows()
                        if column["crypto_name"] == crypto[0]
                    ],
                }
            )
        cache["cached_response"] = final_response
    return cache["cached_response"]


@app.get("/chat_completion")
async def chat_completion(prompt: str):
    current_date = datetime.today().strftime("%Y-%m-%d")

    response = co.generate(
        "Your job is to convert a user input into data that can be used by a code. The user can either request data for a single crypto ('show') or can choose to make a prediction ('predict') with a max date. Your job is to return a string separated by || AND NOTHING ELSE, with first being 'show' or 'predict', second being the cryptocurrency name (Bitcoin, Monero, Litecoin, Dogecoin, XRP, Stellar, Ethereum) and the third being a date. If the date overflows in months/days, you must overflow the years/months too. for show, just give any date. else, give a future date depending on user's input. If the user puts an amount invested, include it next. In the end, give a human like output that makes the investor make a good decision - You are an investment helper. Your statement should be natural and direct, don't advertise anything and don't be overly enthusiastic. Don't say something like 'this is an amazing opportunity'. the current date is "
        + current_date
        + ". Eg output is given in brackets - (predict||Bitcoin||2024-05-05||200||Investing in Bitcoin today ... etc etc.) OR (show||Bitcoin||2021-05-05||0||Summary of the graph). The user's input is: "
        + prompt
    )

    type_of_query, coin_name, date, amount, summary = (
        response.generations[0].strip(" ").split("||")
    )
    print(type_of_query, coin_name, date, amount, summary)

    if type_of_query == "show":
        # Make a normal SQL query to get the data from last three months to the current date
        response = server.query(
            f"SELECT * FROM files.crypto_prices WHERE date > '{(datetime.strptime(current_date, '%Y-%m-%d') - timedelta(days=170)).strftime('%Y-%m-%d')}' AND crypto_name='{coin_name}';"
        ).fetch()

        # The response should be in the form of a list of dictionaries, where each dictionary is a row
        final_response = []
        for row, column in response.iterrows():
            final_response.append(
                {
                    "date": column["date"],
                    "close": column["close"],
                }
            )

        return {
            "prompt": prompt,
            "response": final_response,
            "response_type": type_of_query,
            "crypto_name": coin_name,
            "crypto_code": code,
            "date": date,
            "img_url": url,
            "amount": amount,
            "summary": summary,
        }
    else:
        response = server.query(
            f"SELECT Pred.close, Pred.date, Pred.crypto_name FROM mindsdb.crypto_predictor_new as Pred JOIN files.crypto_prices as Train WHERE Train.date > LATEST AND Train.crypto_name='{coin_name}';"
        ).fetch()
        final_response = []

        for row, column in response.iterrows():
            final_response.append(
                {
                    "date": column["date"],
                    "close": column["close"],
                }
            )

        code = get_crypto_code(coin_name)
        url = f"https://github.com/Pymmdrza/Cryptocurrency_Logos/blob/mainx/PNG/{code.lower() if code else 'BTC'}.png?raw=true"

        return {
            "prompt": prompt,
            "response": final_response,
            "response_type": type_of_query,
            "crypto_name": coin_name,
            "crypto_code": code,
            "date": date,
            "img_url": url,
            "amount": amount,
            "summary": summary,
        }


@app.get("/get_cryptos")
async def get_cryptos():
    response = server.query(
        f"SELECT DISTINCT crypto_name FROM files.crypto_prices;"
    ).fetch()
    final_response = []
    for row, column in response.iterrows():
        final_response.append(column["crypto_name"])
    return final_response


if __name__ == "__main__":
    uvicorn.run(app, port=8000, host="0.0.0.0")
