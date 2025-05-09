import asyncio
import disnake
from disnake.ext import commands, tasks
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
import os
import warnings

# 경고 필터링
warnings.filterwarnings("ignore", category=DeprecationWarning, module="disnake.http")

# MacOS에서 이벤트 루프 정책 설정 (Python 3.13 충돌 해결)
if hasattr(asyncio, 'set_event_loop_policy'):
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

# .env 파일 로드
load_dotenv()

# 봇 인텐트 설정
intents = disnake.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.messages = True

# Bot 설정
bot = commands.InteractionBot(
    intents=intents,
    test_guilds=None  # 전역 명령어로 설정
)

# 메모리 캐시 변수 (채팅 카운트만 Counter 객체로 유지, 나머지는 DB에서 로드)
server_roles = {}
server_chat_counts = {}
server_excluded_roles = {}
last_aggregate_dates = {}
role_streaks = {}

# 데이터베이스 모듈 임포트
import database as db

# MongoDB 기반 함수들 - 기존 SQLite 함수들 대체
def get_role_streak(guild_id, user_id):
    """사용자의 역할 연속 기록을 가져옵니다."""
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 역할 연속 기록을 불러올 수 없습니다")
        return {"type": None, "count": 0}
    
    result = db.get_role_streak(guild_id, user_id)
    
    # 메모리 캐시 업데이트
    if guild_id not in role_streaks:
        role_streaks[guild_id] = {}
    role_streaks[guild_id][user_id] = result
    
    return result

def update_role_streak(guild_id, user_id, role_type):
    """사용자의 역할 연속 기록을 업데이트합니다."""
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 역할 연속 기록을 저장할 수 없습니다")
        return 1
    
    new_streak = db.update_role_streak(guild_id, user_id, role_type)
    
    # 메모리 캐시 업데이트
    if guild_id not in role_streaks:
        role_streaks[guild_id] = {}
    
    role_streaks[guild_id][user_id] = {
        "type": role_type,
        "count": new_streak
    }
    
    return new_streak

def reset_chat_counts(guild_id):
    """특정 길드의 모든 채팅 카운트를 초기화합니다."""
    if guild_id in server_chat_counts:
        server_chat_counts[guild_id].clear()  # Counter 객체 초기화
    
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 채팅 카운트를 초기화할 수 없습니다")
        return
    
    # MongoDB에서 채팅 카운트 삭제
    db.reset_chat_counts(guild_id)
    print(f"[MongoDB] 길드 {guild_id}의 채팅 카운트 초기화 완료")

def save_last_aggregate_date(guild_id):
    """마지막 집계 날짜를 저장합니다."""
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 집계 날짜를 저장할 수 없습니다")
        return
    
    # MongoDB에 저장
    db.save_last_aggregate_date(guild_id)
    print(f"[MongoDB] 길드 {guild_id}의 마지막 집계 날짜 저장 완료")

def get_last_aggregate_date(guild_id):
    """마지막 집계 날짜를 조회합니다."""
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 집계 날짜를 조회할 수 없습니다")
        return None
    
    return db.get_last_aggregate_date(guild_id)

def get_messages_in_period(guild_id, start_date, end_date):
    """특정 기간의 메시지를 조회합니다."""
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 메시지를 조회할 수 없습니다")
        return []
    
    return db.get_messages_in_period(guild_id, start_date, end_date)

# 오래된 메시지 삭제 (MongoDB 기반)
@tasks.loop(hours=24)
async def delete_old_messages():
    """30일 이상 된 메시지를 삭제합니다."""
    if not db.is_mongo_connected():
        print("⚠️ MongoDB 연결 실패: 오래된 메시지를 삭제할 수 없습니다")
        return
    
    from datetime import timedelta
    cutoff_date = datetime.now(db.timezone.utc) - timedelta(days=30)
    
    result = db.messages_collection.delete_many({"timestamp": {"$lt": cutoff_date}})
    print(f"[MongoDB] {result.deleted_count}개의 오래된 메시지 삭제 완료")

@bot.event
async def on_ready():
    global server_roles, server_chat_counts, server_excluded_roles
    try:
        print(f"Logged in as {bot.user.name}")
        print(f"Bot ID: {bot.user.id}")
        
        # 폰트 및 필수 디렉토리 확인
        check_required_files()
        
        # 봇 상태 메시지 설정
        game_activity = disnake.Game(name="通りゃんせ　通りゃんせ")
        await bot.change_presence(activity=game_activity)
        
        # MongoDB에서 데이터 로드
        if db.is_mongo_connected():
            print("MongoDB에서 데이터 로드 중...")
            db.debug_mongodb_data()  # 데이터 상태 확인
            
            # 데이터 로드
            server_roles = db.load_role_data()
            server_excluded_roles = db.load_excluded_role_data()
            
            # 채팅 카운트 로드 및 Counter 객체로 변환
            chat_counts = db.load_chat_counts()
            server_chat_counts = {}
            for guild_id, counts in chat_counts.items():
                server_chat_counts[guild_id] = Counter(counts)
            
            print("MongoDB 데이터 로드 완료!")
        else:
            print("⚠️ MongoDB에 연결되어 있지 않습니다. 봇이 제대로 작동하지 않을 수 있습니다.")
        
        print(f"✅ 봇이 준비되었습니다! (핑: {round(bot.latency * 1000)}ms)")
        
    except Exception as e:
        print(f"Error in on_ready: {e}")
        import traceback
        traceback.print_exc()

# 필수 파일/폴더 확인 함수 추가
def check_required_files():
    """필수 파일 및 폴더 존재 확인"""
    # 필수 디렉토리 목록
    required_dirs = ["OTF", "im", "manual"]
    
    print("\n==== 필수 파일/폴더 확인 ====")
    
    # 현재 디렉토리 표시
    current_dir = os.getcwd()
    print(f"현재 작업 디렉토리: {current_dir}")
    
    # 디렉토리 확인
    for dir_name in required_dirs:
        dir_path = os.path.join(current_dir, dir_name)
        if os.path.exists(dir_path):
            print(f"✅ {dir_name} 디렉토리 존재")
            
            # 디렉토리 내 파일 확인 (최대 5개만 표시)
            try:
                files = os.listdir(dir_path)[:5]
                if files:
                    file_list = ", ".join(files)
                    if len(files) < len(os.listdir(dir_path)):
                        file_list += f" 외 {len(os.listdir(dir_path)) - len(files)}개"
                    print(f"   파일 목록: {file_list}")
                else:
                    print(f"   ⚠️ {dir_name} 디렉토리가 비어 있습니다")
            except Exception as e:
                print(f"   ⚠️ 파일 목록 확인 중 오류: {e}")
        else:
            print(f"❌ {dir_name} 디렉토리가 없습니다")
            
            # 디렉토리 생성 시도
            try:
                os.makedirs(dir_path)
                print(f"   → {dir_name} 디렉토리를 생성했습니다")
            except Exception as e:
                print(f"   ⚠️ 디렉토리 생성 실패: {e}")
    
    print("===============================\n")

@bot.event
async def on_guild_join(guild):
    if db.is_mongo_connected():
        print(f"새로운 서버 참여: {guild.name} (ID: {guild.id})")
        try:
            # 해당 서버의 역할 데이터 로드
            role_data = db.get_guild_role_data(guild.id)
            if role_data:
                server_roles[guild.id] = role_data
                print(f"서버 {guild.id}의 역할 데이터 로드 완료")
                
            # 제외 역할 데이터 로드
            excluded_roles = db.get_guild_excluded_roles(guild.id)
            if excluded_roles:
                server_excluded_roles[guild.id] = excluded_roles
                print(f"서버 {guild.id}의 제외 역할 데이터 로드 완료")
        except Exception as e:
            print(f"⚠️ 서버 {guild.id} 데이터 로드 중 오류 발생: {e}")

@bot.event
async def on_message(message):
    # 봇 메시지 무시
    if message.author.bot or not message.guild:
        return

    # !list 명령어는 항상 허용 (auth.py에서 처리)
    if message.content.lower().startswith('!list'):
        return

    # 서버 인증 확인
    from commands.auth import is_guild_authorized
    if not is_guild_authorized(message.guild.id):
        # 인증되지 않은 서버는 메시지 처리 중단
        return

    # 메시지 처리 로직
    guild_id = message.guild.id
    user_id = message.author.id
    
    if guild_id not in server_chat_counts:
        server_chat_counts[guild_id] = Counter()

    excluded_roles = server_excluded_roles.get(guild_id, [])
    if any(role.id in excluded_roles for role in message.author.roles):
        return

    # 채팅 카운트 증가
    server_chat_counts[guild_id][user_id] += 1
    
    # MongoDB에만 저장
    if db.is_mongo_connected():
        db.save_chat_count(guild_id, user_id, server_chat_counts[guild_id][user_id])
        
        # 메시지도 MongoDB에 저장
        db.save_message(guild_id, user_id, message.id, message.created_at)
    else:
        print("⚠️ MongoDB에 연결되지 않아 데이터를 저장할 수 없습니다")

# 에러 핸들링 이벤트 추가
@bot.event
async def on_slash_command_error(inter, error):
    import traceback
    print(f"명령어 오류 발생 ({inter.data.name}): {error}")
    traceback.print_exc()

# 봇 실행 (환경 변수에서 토큰 가져오기)
TOKEN = os.getenv('DISCORD_TOKEN')

# Import commands after all definitions
import commands.test
import commands.ping
import commands.role_set
import commands.role_exclude
import commands.leaderboard
import commands.aggregate
import commands.reset_streak
import commands.omikuji
import commands.role_color
import commands.auth
import commands.manual
import commands.tenor

# 봇 실행
if TOKEN:
    masked_token = TOKEN[:4] + '*' * (len(TOKEN) - 8) + TOKEN[-4:]
    print(f"토큰 로드 성공: {masked_token}")
    bot.run(TOKEN)
else:
    print("❌ 토큰을 찾을 수 없는 것이다! .env 파일을 확인하는 것이다.")