def get_account_holdings():
    result = _signed_post("private/get-account-summary")
    balances = result.get("accounts", [])
    holdings = []

    for acc in balances:
        print(f"🔍 返 回 账 户 信 息 : {acc}")
        currency = acc.get("currency")
        balance = float(acc.get("balance", 0))
        if balance > 0:
            holdings.append({
                "currency": currency,
                "total": balance
            })

    return holdings

def get_supported_symbols():
    url = f"{BASE_URL}/public/get-instruments"
    try:
        response = requests.get(url, params={"instrument_type": "SPOT"})
        data = response.json()
    except Exception as e:
        print(f"❌ 获取币种列表失败（网络或解析错误）：{e}")
        return set()

    if data.get("code") != 0:
        print(f"❌ 获取币种列表失败：{data.get('message', 'Unknown error')} (code={data.get('code')})")
        return set()

    instruments = data.get("result", {}).get("instruments", [])
    usdt_pairs = set()

    for item in instruments:
        try:
            if item.get("quote_currency") == "USDT":
                usdt_pairs.add(item["instrument_name"])
        except:
            continue

    print(f"✅ 共识别 {len(usdt_pairs)} 个支持 USDT 的币种交易对")
    return usdt_pairs
    
def filter_valid_holdings(holdings):
    valid_symbols = get_supported_symbols()
    filtered = []

    for h in holdings:
        symbol = f"{h['currency']}_USDT"
        if symbol in valid_symbols:
            filtered.append({
                "symbol": symbol,
                "amount": h["total"]
            })
        else:
            print(f"⚠️ 跳 过 不 支 持 的 币 种: {h['currency']}")

    return filtered