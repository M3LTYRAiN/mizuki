import os
from dotenv import load_dotenv
import pymongo
from datetime import datetime, timezone  # timezone 추가

# 환경 변수 로드
load_dotenv()

# MongoDB 연결 문자열
MONGO_URI = os.getenv("MONGODB_URI")

# MongoDB 연결 여부 확인
DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "False").lower() == "true"

# MongoDB 클라이언트
if MONGO_URI and not DEVELOPMENT_MODE:
    try:
        print(f"MongoDB 연결 시도 중... URI: {MONGO_URI[:20]}...")
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # 연결 테스트
        client.server_info()
        db = client.chatzipbot
        
        # 컬렉션 설정
        roles_collection = db.roles
        excluded_roles_collection = db.excluded_roles
        chat_counts_collection = db.chat_counts
        messages_collection = db.messages
        aggregate_dates_collection = db.aggregate_dates
        role_streaks_collection = db.role_streaks
        auth_codes_collection = db.auth_codes
        authorized_guilds_collection = db.authorized_guilds
        
        print("MongoDB 연결 성공!")
        print(f"사용 가능한 데이터베이스: {client.list_database_names()}")
        print(f"컬렉션: {db.list_collection_names()}")
    except Exception as e:
        print(f"MongoDB 연결 실패: {e}")
        client = None
        db = None
else:
    print("개발 모드 또는 MongoDB 연결 문자열이 없습니다. 로컬 SQLite를 사용합니다.")
    client = None
    db = None

# MongoDB 헬퍼 함수
def is_mongo_connected():
    return db is not None

# 역할 데이터 로드
def load_role_data():
    if not is_mongo_connected():
        return {}
        
    result = {}
    for doc in roles_collection.find():
        guild_id = doc["guild_id"]
        result[guild_id] = {
            "first": doc["first_role_id"],
            "other": doc["other_role_id"]
        }
    return result

# 역할 데이터 저장
def save_role_data(guild_id, first_role_id, other_role_id):
    if not is_mongo_connected():
        return
        
    roles_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "guild_id": guild_id,
            "first_role_id": first_role_id,
            "other_role_id": other_role_id,
            "updated_at": datetime.now(timezone.utc)  # utcnow() 대신 사용
        }},
        upsert=True
    )

# 제외 역할 로드
def load_excluded_role_data():
    if not is_mongo_connected():
        return {}
        
    result = {}
    for doc in excluded_roles_collection.find():
        guild_id = doc["guild_id"]
        if guild_id not in result:
            result[guild_id] = []
        result[guild_id].append(doc["role_id"])
    return result

# 제외 역할 저장
def save_excluded_role_data(guild_id, excluded_roles):
    if not is_mongo_connected():
        return
        
    # 기존 데이터 삭제
    excluded_roles_collection.delete_many({"guild_id": guild_id})
    
    # 새 데이터 저장
    if excluded_roles:
        documents = [
            {"guild_id": guild_id, "role_id": role_id, "updated_at": datetime.now(timezone.utc)}  # 수정
            for role_id in excluded_roles
        ]
        excluded_roles_collection.insert_many(documents)

# 채팅 카운트 로드
def load_chat_counts():
    if not is_mongo_connected():
        return {}
        
    result = {}
    for doc in chat_counts_collection.find():
        guild_id = doc["guild_id"]
        user_id = doc["user_id"]
        count = doc["count"]
        
        if guild_id not in result:
            result[guild_id] = {}
        result[guild_id][user_id] = count
    return result

# 채팅 카운트 저장
def save_chat_count(guild_id, user_id, count):
    if not is_mongo_connected():
        return
        
    chat_counts_collection.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$set": {
            "guild_id": guild_id,
            "user_id": user_id,
            "count": count,
            "updated_at": datetime.now(timezone.utc)  # 수정
        }},
        upsert=True
    )

# MongoDB 데이터 확인 함수
def debug_mongodb_data():
    """MongoDB에 저장된 데이터 상태를 확인하는 함수"""
    if not is_mongo_connected():
        print("MongoDB에 연결되지 않았습니다.")
        return
    
    try:
        print("\n=== MongoDB 데이터 상태 ===")
        
        # 컬렉션 목록
        collections = db.list_collection_names()
        print(f"컬렉션 목록: {collections}")
        
        # 주요 컬렉션 카운트
        role_count = roles_collection.count_documents({})
        excluded_roles_count = excluded_roles_collection.count_documents({})
        chat_counts_count = chat_counts_collection.count_documents({})
        auth_guilds_count = authorized_guilds_collection.count_documents({})
        
        print(f"역할 데이터: {role_count}개")
        print(f"제외 역할: {excluded_roles_count}개")
        print(f"채팅 카운트: {chat_counts_count}개")
        print(f"인증된 서버: {auth_guilds_count}개")
        
        # 샘플 데이터 출력
        if auth_guilds_count > 0:
            guilds = list(authorized_guilds_collection.find().limit(3))
            print(f"인증 서버 샘플: {guilds}")
            
        print("=== 데이터 확인 완료 ===\n")
    except Exception as e:
        print(f"데이터 확인 중 오류: {e}")

# 그 외 필요한 함수들...
