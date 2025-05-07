import requests
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any

class FuelPriceService:
    
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        logging.info("FuelPriceService initialized")







    def get_state_code(self, city_name: str):
        api_key = "cf3448e43c32400593094516af6cf1bd"
        url = "https://api.opencagedata.com/geocode/v1/json"
        params = {
            "q": city_name,
            "key": api_key,
            "countrycode": "us",  # 限制美国
            "limit": 1
        }

        r = requests.get(url, params=params)
        if r.status_code != 200:
            print("❌ 请求失败:", r.status_code)
            return None

        data = r.json()
        if not data["results"]:
            print("❌ 没有找到任何结果")
            return None

        components = data["results"][0]["components"]
        print("📍 详细地址组件:", components)

        # 获取州代码（如 CA）
        return components.get("state_code") or components.get("state")
   
   
    
   


    def get_series_id_by_city(self, city: str) -> str:
        # ⛔ 在没有 EIA 提供完整映射表的情况下，我们只能手动维护常见城市的 series ID
        city_to_series = {
            "los angeles": "EMM_EPMR_PTE_CA_LA_DPG",
            "houston": "EMM_EPMR_PTE_TX_HOU_DPG",
            "new york": "EMM_EPMR_PTE_NY_NYC_DPG",
            "chicago": "EMM_EPMR_PTE_IL_CHI_DPG",
            "san francisco": "EMM_EPMR_PTE_CA_SF_DPG",
            "us average": "EMM_EPMR_PTE_NUS_DPG"
        }
        return city_to_series.get(city.lower())

    def get_gas_price(self, city: str, start_date: str, end_date: str):
        series_id = "EMM_EPMR_PTE_NUS_DPG"
        if not series_id:
            print(f"❌ No known series ID for city '{city}'.")
            return

        url = (
            f"https://api.eia.gov/v2/petroleum/pri/gnd/data/"
            f"?api_key={self.api_key}"
            f"&frequency=weekly"
            f"&data[0]=value"
            f"&facets[series][]={series_id}"
            f"&start=2025-04-01"
            f"&end=2025-05-01"
            f"&sort[0][column]=period&sort[0][direction]=asc"
            f"&offset=0&length=500"
        )

        response = requests.get(url)
        data = response.json()
        print(f"data: {data}")
        if "response" not in data:
            print("❌ Error:", data.get("error", "Unknown error"))
            return

        for row in data["response"]["data"]:
            print(f"{row['period']}: ${row['value']} per gallon")

## 具体到城市，现在是全美周平均油价
