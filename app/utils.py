from fastapi import HTTPException

def validate_business_hours(time_str: str):
    try:
        hour = int(time_str.split(":")[0])
        if not (9 <= hour <= 18):
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail="預約失敗：營業時間僅限 09:00 至 18:00")