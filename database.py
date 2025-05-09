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
if (MONGO_URI and not DEVELOPMENT_MODE):
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
        print("⚠️ MongoDB에 연결되지 않아 제외 역할을 로드할 수 없습니다")
        return {}

    result = {}
    try:
        # 집계 쿼리를 사용하여 서버별 역할 목록 한번에 가져오기
        pipeline = [
            {"$group": {"_id": "$guild_id", "role_ids": {"$push": "$role_id"}}}
        ]

        # 결과 처리
        for doc in excluded_roles_collection.aggregate(pipeline):
            guild_id = doc["_id"]  # guild_id가 _id로 그룹화됨
            result[guild_id] = doc["role_ids"]

        # 로그 추가
        guild_count = len(result)
        role_count = sum(len(roles) for roles in result.values())
        print(f"제외 역할 로드 완료: {guild_count}개 서버, 총 {role_count}개 역할")

        # 처음 몇 개의 서버만 상세 정보 출력
        for guild_id, roles in list(result.items())[:3]:
            print(f"  서버 {guild_id}: {len(roles)}개 제외 역할 - {roles}")

        return result
    except Exception as e:
        print(f"⚠️ 제외 역할 로드 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return {}

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

def save_message(guild_id, user_id, message_id, timestamp):
    """메시지를 MongoDB에 저장합니다"""
    if not is_mongo_connected():
        return

    messages_collection.insert_one({
        "guild_id": guild_id,
        "user_id": user_id,
        "message_id": message_id,
        "timestamp": timestamp,
        "created_at": datetime.now(timezone.utc)
    })

# 추가: 메시지 조회 함수
def get_messages_in_period(guild_id, start_date, end_date):
    """특정 기간의 메시지를 조회합니다"""
    if not is_mongo_connected():
        return []

    cursor = messages_collection.find({
        "guild_id": guild_id,
        "timestamp": {"$gte": start_date, "$lte": end_date}
    })

    return [{"user_id": doc["user_id"]} for doc in cursor]

# 추가: 집계 날짜 저장 함수
def save_last_aggregate_date(guild_id):
    """마지막 집계 날짜를 저장합니다"""
    if not is_mongo_connected():
        return

    aggregate_dates_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "guild_id": guild_id,
            "last_aggregate_date": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

# 추가: 집계 날짜 조회 함수
def get_last_aggregate_date(guild_id):
    """마지막 집계 날짜를 조회합니다"""
    if not is_mongo_connected():
        return None

    doc = aggregate_dates_collection.find_one({"guild_id": guild_id})
    return doc["last_aggregate_date"] if doc else None

# 추가: 채팅 카운트 초기화 함수
def reset_chat_counts(guild_id):
    """특정 길드의 모든 채팅 카운트를 초기화합니다"""
    if not is_mongo_connected():
        return

    chat_counts_collection.delete_many({"guild_id": guild_id})

# 추가: 역할 연속 기록 조회 함수
def get_role_streak(guild_id, user_id):
    """특정 사용자의 역할 연속 기록을 조회합니다"""
    if not is_mongo_connected():
        return {"type": None, "count": 0}

    doc = role_streaks_collection.find_one({"guild_id": guild_id, "user_id": user_id})
    if doc:
        return {"type": doc["role_type"], "count": doc["streak_count"]}
    return {"type": None, "count": 0}

# 추가: 역할 연속 기록 업데이트 함수
def update_role_streak(guild_id, user_id, role_type):
    """특정 사용자의 역할 연속 기록을 업데이트합니다"""
    if not is_mongo_connected():
        return 1

    # 현재 기록 가져오기
    current = get_role_streak(guild_id, user_id)

    # 새로운 연속 기록 계산
    new_streak = current["count"] + 1 if current["type"] == role_type else 1

    # 업데이트
    role_streaks_collection.update_one(
        {"guild_id": guild_id, "user_id": user_id},
        {"$set": {
            "role_type": role_type,
            "streak_count": new_streak,
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )

    return new_streak

# 연속 기록 초기화 함수
def reset_role_streaks(guild_id):
    """특정 길드의 모든 연속 기록을 초기화합니다"""
    if not is_mongo_connected():
        return 0

    result = role_streaks_collection.update_many(
        {"guild_id": guild_id},
        {"$set": {
            "streak_count": 0,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    return result.modified_count

# 추가: 인증 코드 생성 함수
def generate_auth_code():
    """16자리 무작위 인증 코드를 생성합니다"""
    if not is_mongo_connected():
        return None

    import random
    import string

    # 랜덤 코드 생성
    code_chars = string.ascii_letters + string.digits
    code = ''.join(random.choice(code_chars) for _ in range(16))

    # MongoDB에 저장
    auth_codes_collection.insert_one({
        "code": code,
        "created_at": datetime.now(timezone.utc),
        "used": False,
        "used_by": None
    })

    return code

# 추가: 인증 코드 유효성 검사 함수
def validate_auth_code(code):
    """인증 코드의 유효성을 검사합니다"""
    if not is_mongo_connected():
        return False, "데이터베이스에 연결할 수 없습니다"

    doc = auth_codes_collection.find_one({"code": code})
    if not doc:
        return False, "유효하지 않은 인증 코드입니다"

    if doc.get("used", False):
        return False, "이미 사용된 인증 코드입니다"

    return True, "유효한 인증 코드입니다"

# 추가: 인증 코드 사용 처리 함수
def use_auth_code(code, guild_id):
    """인증 코드를 사용 처리하고 서버를 인증합니다"""
    if not is_mongo_connected():
        return False

    # 코드 사용 처리
    auth_codes_collection.update_one(
        {"code": code},
        {"$set": {
            "used": True,
            "used_by": guild_id,
            "used_at": datetime.now(timezone.utc)
        }}
    )

    # 서버 인증 상태 저장
    authorized_guilds_collection.update_one(
        {"guild_id": guild_id},
        {"$set": {
            "guild_id": guild_id,
            "authorized_at": datetime.now(timezone.utc),
            "auth_code": code
        }},
        upsert=True
    )

    return True

# 추가: 인증된 서버 목록 조회 함수
def load_authorized_guilds():
    """인증된 서버 목록을 조회합니다"""
    if not is_mongo_connected():
        return {}

    result = {}
    for doc in authorized_guilds_collection.find():
        result[doc["guild_id"]] = True

    return result

# 추가: 서버 인증 상태 확인 함수
def is_guild_authorized(guild_id):
    """서버가 인증되었는지 확인합니다"""
    if not is_mongo_connected():
        return False

    return authorized_guilds_collection.find_one({"guild_id": guild_id}) is not None

# 서버 인증 취소 함수
def delete_authorized_guild(guild_id):
    """특정 서버의 인증을 취소합니다"""
    if not is_mongo_connected():
        return False

    result = authorized_guilds_collection.delete_one({"guild_id": guild_id})
    return result.deleted_count > 0

# 인증 코드 삭제 함수
def delete_auth_code(code):
    """인증 코드를 삭제합니다"""
    if not is_mongo_connected():
        return False

    result = auth_codes_collection.delete_one({"code": code})
    return result.deleted_count > 0


# 역할 데이터 로드 함수 개선
def load_role_data():
    if not is_mongo_connected():
        print("⚠️ MongoDB에 연결되지 않아 역할 데이터를 로드할 수 없습니다")
        return {}

    result = {}
    try:
        # 모든 역할 설정 불러오기
        cursor = roles_collection.find()
        roles_count = 0
        
        for doc in cursor:
            guild_id = doc["guild_id"]
            result[guild_id] = {
                "first": doc["first_role_id"],
                "other": doc["other_role_id"]
            }
            roles_count += 1
            
        print(f"역할 데이터 로드 완료: {roles_count}개 서버")
        return result
    except Exception as e:
        print(f"⚠️ 역할 데이터 로드 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return {}

# 제외 역할 저장 함수 개선
def save_excluded_role_data(guild_id, excluded_roles):
    if not is_mongo_connected():
        print(f"⚠️ MongoDB에 연결되지 않아 제외 역할을 저장할 수 없습니다 (길드: {guild_id})")
        return

    try:
        # 기존 데이터 삭제
        delete_result = excluded_roles_collection.delete_many({"guild_id": guild_id})
        
        # 새 데이터 저장
        if excluded_roles:
            documents = [
                {"guild_id": guild_id, "role_id": role_id, "updated_at": datetime.now(timezone.utc)}
                for role_id in excluded_roles
            ]
            insert_result = excluded_roles_collection.insert_many(documents)
            print(f"제외 역할 저장 완료: 길드 {guild_id}, {len(excluded_roles)}개 역할, 삭제: {delete_result.deleted_count}개, 삽입: {len(insert_result.inserted_ids)}개")
        else:
            print(f"제외 역할 초기화: 길드 {guild_id}, 삭제: {delete_result.deleted_count}개")
    except Exception as e:
        print(f"⚠️ 제외 역할 저장 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

# 특정 서버의 역할 데이터만 로드하는 함수
def get_guild_role_data(guild_id):
    if not is_mongo_connected():
        print(f"⚠️ MongoDB에 연결되지 않아 서버 {guild_id}의 역할 데이터를 로드할 수 없습니다")
        return None

    try:
        doc = roles_collection.find_one({"guild_id": guild_id})
        if doc:
            return {
                "first": doc["first_role_id"],
                "other": doc["other_role_id"]
            }
        else:
            print(f"서버 {guild_id}의 역할 데이터가 없습니다")
            return None
    except Exception as e:
        print(f"⚠️ 서버 {guild_id}의 역할 데이터 로드 중 오류 발생: {e}")
        return None

# 특정 서버의 제외 역할 데이터만 로드하는 함수
def get_guild_excluded_roles(guild_id):
    if not is_mongo_connected():
        print(f"⚠️ MongoDB에 연결되지 않아 서버 {guild_id}의 제외 역할 데이터를 로드할 수 없습니다")
        return None

    try:
        cursor = excluded_roles_collection.find({"guild_id": guild_id})
        excluded_roles = [doc["role_id"] for doc in cursor]
        
        if excluded_roles:
            print(f"서버 {guild_id}의 제외 역할 {len(excluded_roles)}개 로드됨")
            return excluded_roles
        else:
            print(f"서버 {guild_id}의 제외 역할 데이터가 없습니다")
            return []
    except Exception as e:
        print(f"⚠️ 서버 {guild_id}의 제외 역할 데이터 로드 중 오류 발생: {e}")
        return []