import json
import datetime
from app import SECTOR_LIST, STOCK_DB, TechProvider, advanced_quant_filter

start_date = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()

results = []

for sector, tickers in SECTOR_LIST.items():
    if not tickers:
        results.append({"sector": sector, "ticker": None, "name": None, "rows": 0, "passed": False, "reason": "no_tickers_in_sector"})
        continue
    for t in tickers:
        rec = {"sector": sector, "ticker": t, "name": STOCK_DB.get(t, {}).get("name"), "rows": 0, "passed": False, "reason": None}
        try:
            df = TechProvider.fetch_data(t, start_date)
            if df is None:
                rec['rows'] = 0
                rec['reason'] = 'no_data_or_too_few_rows'
            else:
                rec['rows'] = len(df)
                try:
                    res = advanced_quant_filter(t, start_date)
                    rec['passed'] = res is not None
                    rec['reason'] = res.get('status') if res else 'filtered_out'
                except Exception as fe:
                    rec['reason'] = f'filter_error:{str(fe)}'
        except Exception as e:
            rec['rows'] = 0
            rec['reason'] = f'fetch_error:{str(e)}'
        results.append(rec)

print(json.dumps(results, ensure_ascii=False, indent=2))
