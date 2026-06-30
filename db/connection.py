import pymysql
from config import DB_CONFIG

def get_db():
    return pymysql.connect(
        **DB_CONFIG,                              # config.py의 딕셔너리 언팩
        cursorclass=pymysql.cursors.DictCursor    # 결과를 딕셔너리로 반환
    )