import os
from dotenv import load_dotenv
import pymongo

# 환경 변수 로드
load_dotenv()

# MongoDB 연결 문자열 가져오기
MONGO_URI = os.getenv("MONGODB_URI")

if not MONGO_URI:
    print("❌ MongoDB 연결 문자열이 없습니다!")
    exit(1)

try:
    # 연결 시도
    print("MongoDB 연결 시도 중...")
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    
    # 서버 정보 가져와서 연결 확인
    server_info = client.server_info()
    
    print("✅ MongoDB 연결 성공!")
    print(f"서버 버전: {server_info.get('version')}")
    
    # 데이터베이스 목록 확인
    database_names = client.list_database_names()
    print(f"사용 가능한 데이터베이스: {database_names}")
    
    # chatzipbot 데이터베이스 컬렉션 확인
    db = client.chatzipbot
    collections = db.list_collection_names()
    print(f"chatzipbot 데이터베이스의 컬렉션: {collections}")
    
except pymongo.errors.ServerSelectionTimeoutError:
    print("❌ MongoDB 연결 실패: 서버에 연결할 수 없습니다. URI를 확인하세요.")
except pymongo.errors.OperationFailure as e:
    print(f"❌ MongoDB 인증 실패: {e}")
except Exception as e:
    print(f"❌ 오류 발생: {e}")
finally:
    if 'client' in locals():
        client.close()
