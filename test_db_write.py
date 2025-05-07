from database import db, is_mongo_connected
import datetime

if is_mongo_connected():
    # 테스트 컬렉션
    test_collection = db.db.test_collection
    
    # 현재 시간으로 테스트 문서 작성
    test_data = {
        "test_id": 1,
        "message": "MongoDB 연결 테스트",
        "timestamp": datetime.datetime.utcnow()
    }
    
    # 데이터 삽입
    result = test_collection.insert_one(test_data)
    
    # 결과 확인
    if result.inserted_id:
        print(f"✅ 테스트 데이터 저장 성공! ID: {result.inserted_id}")
        
        # 저장된 데이터 확인
        saved_data = test_collection.find_one({"test_id": 1})
        print(f"저장된 데이터: {saved_data}")
    else:
        print("❌ 데이터 저장 실패!")
else:
    print("❌ MongoDB에 연결되지 않았습니다.")
