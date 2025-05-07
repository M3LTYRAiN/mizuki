import sqlite3
import pymongo
import os
from dotenv import load_dotenv
from datetime import datetime
from collections import Counter

def migrate_to_mongodb():
    # 환경 변수 로드
    load_dotenv()
    MONGO_URI = os.getenv("MONGODB_URI")
    
    if not MONGO_URI:
        print("MongoDB 연결 문자열이 설정되지 않았습니다.")
        return
    
    # SQLite 연결
    print("SQLite 데이터베이스 연결...")
    sqlite_conn = sqlite3.connect('bot_data.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # MongoDB 연결
    print("MongoDB 연결...")
    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client.chatzipbot
    
    # 역할 데이터 마이그레이션
    print("역할 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT guild_id, first_role_id, other_role_id FROM roles")
    roles_data = sqlite_cursor.fetchall()
    
    for guild_id, first_role_id, other_role_id in roles_data:
        db.roles.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "guild_id": guild_id,
                "first_role_id": first_role_id,
                "other_role_id": other_role_id,
                "migrated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    print(f"역할 데이터 {len(roles_data)}개 마이그레이션 완료")
    
    # 제외 역할 데이터 마이그레이션
    print("제외 역할 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT guild_id, role_id FROM excluded_roles")
    excluded_roles_data = sqlite_cursor.fetchall()
    
    # 길드별로 그룹화
    excluded_roles_by_guild = {}
    for guild_id, role_id in excluded_roles_data:
        if guild_id not in excluded_roles_by_guild:
            excluded_roles_by_guild[guild_id] = []
        excluded_roles_by_guild[guild_id].append(role_id)
    
    # 데이터 저장
    for guild_id, role_ids in excluded_roles_by_guild.items():
        for role_id in role_ids:
            db.excluded_roles.update_one(
                {"guild_id": guild_id, "role_id": role_id},
                {"$set": {
                    "guild_id": guild_id,
                    "role_id": role_id,
                    "migrated_at": datetime.utcnow()
                }},
                upsert=True
            )
    
    print(f"제외 역할 데이터 {len(excluded_roles_data)}개 마이그레이션 완료")
    
    # 채팅 카운트 마이그레이션
    print("채팅 카운트 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT guild_id, user_id, count FROM chat_counts")
    chat_counts_data = sqlite_cursor.fetchall()
    
    for guild_id, user_id, count in chat_counts_data:
        db.chat_counts.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": {
                "guild_id": guild_id,
                "user_id": user_id,
                "count": count,
                "migrated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    print(f"채팅 카운트 데이터 {len(chat_counts_data)}개 마이그레이션 완료")
    
    # 집계 날짜 마이그레이션
    print("집계 날짜 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT guild_id, last_aggregate_date FROM aggregate_dates")
    aggregate_dates_data = sqlite_cursor.fetchall()
    
    for guild_id, last_aggregate_date in aggregate_dates_data:
        db.aggregate_dates.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "guild_id": guild_id,
                "last_aggregate_date": last_aggregate_date,
                "migrated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    print(f"집계 날짜 데이터 {len(aggregate_dates_data)}개 마이그레이션 완료")
    
    # 역할 연속 기록 마이그레이션
    print("역할 연속 기록 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT guild_id, user_id, role_type, streak_count FROM role_streaks")
    role_streaks_data = sqlite_cursor.fetchall()
    
    for guild_id, user_id, role_type, streak_count in role_streaks_data:
        db.role_streaks.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": {
                "guild_id": guild_id,
                "user_id": user_id,
                "role_type": role_type,
                "streak_count": streak_count,
                "migrated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    print(f"역할 연속 기록 데이터 {len(role_streaks_data)}개 마이그레이션 완료")
    
    # 인증 코드 마이그레이션
    print("인증 코드 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT code, created_at, used, used_by FROM auth_codes")
    auth_codes_data = sqlite_cursor.fetchall()
    
    for code, created_at, used, used_by in auth_codes_data:
        db.auth_codes.update_one(
            {"code": code},
            {"$set": {
                "code": code,
                "created_at": created_at,
                "used": used == 1,  # SQLite 저장된 값은 0 또는 1입니다
                "used_by": used_by,
                "migrated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    print(f"인증 코드 데이터 {len(auth_codes_data)}개 마이그레이션 완료")
    
    # 인증된 서버 마이그레이션
    print("인증된 서버 데이터 마이그레이션...")
    sqlite_cursor.execute("SELECT guild_id, authorized_at, auth_code FROM authorized_guilds")
    authorized_guilds_data = sqlite_cursor.fetchall()
    
    for guild_id, authorized_at, auth_code in authorized_guilds_data:
        db.authorized_guilds.update_one(
            {"guild_id": guild_id},
            {"$set": {
                "guild_id": guild_id,
                "authorized_at": authorized_at,
                "auth_code": auth_code,
                "migrated_at": datetime.utcnow()
            }},
            upsert=True
        )
    
    print(f"인증된 서버 데이터 {len(authorized_guilds_data)}개 마이그레이션 완료")
    
    print("마이그레이션 완료!")
    sqlite_conn.close()

if __name__ == "__main__":
    migrate_to_mongodb()