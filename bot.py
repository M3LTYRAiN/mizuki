import asyncio
import disnake
from disnake.ext import commands, tasks
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
import os
import warnings
import pytz  # pytz 모듈 추가

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

        check_required_files()
        game_activity = disnake.Game(name="通りゃんせ　通りゃんせ")
        await bot.change_presence(activity=game_activity)

        print("\n==== 봇 초기화 및 데이터 로드 ====")
        if db.is_mongo_connected():
            print("MongoDB 연결 확인됨, 데이터 로드 시작...")

            # 1. 역할 설정 데이터 (전체 로드)
            print("\n역할 설정 데이터 로드 중...")
            loaded_roles = db.load_role_data() # DB에서 모든 역할 데이터 로드
            if loaded_roles:
                # guild_id를 정수형으로 변환하여 저장
                for guild_id_str, role_data in loaded_roles.items():
                    try:
                        guild_id_int = int(guild_id_str)
                        server_roles[guild_id_int] = role_data
                    except ValueError:
                        print(f"잘못된 guild_id 형식: {guild_id_str}")
                print(f"역할 데이터 로드 완료: {len(server_roles)}개 서버")
                print(f"샘플 데이터 (처음 3개): {list(server_roles.items())[:3]}")
            else:
                print("DB에서 로드된 역할 데이터가 없습니다.")

            # 2. 제외 역할 데이터 (전체 로드)
            print("\n제외 역할 데이터 로드 중...")
            loaded_excluded_roles = db.load_excluded_role_data()
            if loaded_excluded_roles:
                for guild_id_str, roles in loaded_excluded_roles.items():
                    try:
                        guild_id_int = int(guild_id_str)
                        server_excluded_roles[guild_id_int] = roles
                    except ValueError:
                         print(f"잘못된 guild_id 형식 (제외 역할): {guild_id_str}")
                print(f"제외 역할 데이터 로드 완료: {len(server_excluded_roles)}개 서버")
                print(f"샘플 데이터 (처음 3개): {list(server_excluded_roles.items())[:3]}")
            else:
                print("DB에서 로드된 제외 역할 데이터가 없습니다.")
            
            # 3. 채팅 카운트 데이터 로드 (기존 코드 유지)
            print("\n채팅 카운트 데이터 로드 중...")
            loaded_chat_counts = db.load_chat_counts()
            if loaded_chat_counts:
                for guild_id, counts in loaded_chat_counts.items():
                    server_chat_counts[guild_id] = Counter(counts)
                print(f"채팅 카운트 로드 완료: {len(server_chat_counts)}개 서버, "
                      f"총 {sum(len(counts) for counts in server_chat_counts.values())}명의 사용자")
                for guild_id_key in list(server_chat_counts.keys())[:3]:
                    user_count = len(server_chat_counts[guild_id_key])
                    message_count = sum(server_chat_counts[guild_id_key].values())
                    print(f"  서버 {guild_id_key}: {user_count}명, {message_count}개 메시지")
            else:
                print("DB에서 로드된 채팅 카운트 데이터가 없습니다.")

            # 4. 각 서버별 데이터 재검증 및 누락된 데이터 로드
            print("\n참여 중인 모든 서버 데이터 검증 및 추가 로드 중...")
            for guild in bot.guilds:
                guild_id = guild.id
                print(f"\n서버 {guild_id} ({guild.name}) 데이터 확인:")

                # 역할 데이터 확인 및 로드
                if guild_id not in server_roles:
                    print(f"  역할 데이터 메모리에 없음, DB에서 직접 로드 시도...")
                    role_data = db.get_guild_role_data(guild_id)
                    if role_data:
                        server_roles[guild_id] = role_data
                        print(f"  ✓ DB에서 역할 데이터 직접 로드 성공: {role_data}")
                    else:
                        print(f"  - DB에도 역할 데이터 없음")
                else:
                    print(f"  ✅ 역할 데이터 메모리에 있음: {server_roles[guild_id]}")

                # 제외 역할 데이터 확인 및 로드
                if guild_id not in server_excluded_roles:
                    print(f"  제외 역할 데이터 메모리에 없음, DB에서 직접 로드 시도...")
                    excluded_roles = db.get_guild_excluded_roles(guild_id)
                    if excluded_roles:
                        server_excluded_roles[guild_id] = excluded_roles
                        print(f"  ✓ DB에서 제외 역할 데이터 직접 로드 성공: {len(excluded_roles)}개")
                    else:
                        print(f"  - DB에도 제외 역할 데이터 없음")
                else:
                    print(f"  ✅ 제외 역할 데이터 메모리에 있음: {len(server_excluded_roles[guild_id])}개")
                
                # 채팅 카운트 데이터 확인 및 로드 (on_message에서도 처리하지만, 시작 시점에도 확인)
                if guild_id not in server_chat_counts or not server_chat_counts[guild_id]:
                    print(f"  채팅 카운트 데이터 메모리에 없음, DB에서 직접 로드 시도...")
                    guild_chat_counts = db.get_guild_chat_counts(guild_id)
                    if guild_chat_counts:
                        server_chat_counts[guild_id] = Counter(guild_chat_counts)
                        print(f"  ✓ DB에서 채팅 카운트 직접 로드 성공: {len(guild_chat_counts)}개 항목")
                    else:
                        server_chat_counts[guild_id] = Counter() # 데이터 없으면 빈 카운터
                        print(f"  - DB에도 채팅 카운트 데이터 없음, 빈 카운터 생성")
                else:
                     print(f"  ✅ 채팅 카운트 데이터 메모리에 있음: {len(server_chat_counts[guild_id])}개 항목")


        # 최종 로드 결과 확인
        print("\n==== 데이터 로드 결과 ====")
        print(f"역할 설정 서버: {len(server_roles)}개")
        print(f"제외 역할 서버: {len(server_excluded_roles)}개")
        print(f"채팅 카운트 서버: {len(server_chat_counts)}개")
        print("=========================\n")

        delete_old_messages.start()

    except Exception as e:
        print(f"Error in on_ready: {e}")
        import traceback
        traceback.print_exc()

# 필수 파일/폴더 확인 함수 추가
def check_required_files():
    """필수 파일 및 폴더 존재 확인"""
    # 필수 디렉토리 목록 (manual 제거)
    required_dirs = ["OTF", "im"]

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
    """새로운 서버에 참여하거나 봇이 시작될 때 해당 서버의 데이터를 로드"""
    if db.is_mongo_connected():
        print(f"서버 데이터 로드: {guild.name} (ID: {guild.id})")
        try:
            # 해당 서버의 역할 데이터 로드 (기존에 메모리에 있어도 갱신)
            role_data = db.get_guild_role_data(guild.id)
            if role_data:
                server_roles[guild.id] = role_data
                print(f"✓ 서버 {guild.id}({guild.name})의 역할 데이터 로드 완료: {role_data}")
            else:
                print(f"- 서버 {guild.id}({guild.name})의 역할 데이터 없음")

            # 제외 역할 데이터 로드 (기존에 메모리에 있어도 갱신)
            excluded_roles = db.get_guild_excluded_roles(guild.id)
            if excluded_roles:
                server_excluded_roles[guild.id] = excluded_roles
                print(f"✓ 서버 {guild.id}({guild.name})의 제외 역할 데이터 로드 완료: {len(excluded_roles)}개")
            else:
                print(f"- 서버 {guild.id}({guild.name})의 제외 역할 데이터 없음")
        except Exception as e:
            print(f"⚠️ 서버 {guild.id}({guild.name}) 데이터 로드 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()

@bot.event
async def on_message(message):
    # 봇 메시지 무시
    if message.author.bot or not message.guild:
        return

    # 포럼 채널 메시지 무시 (추가된 부분)
    if hasattr(message.channel, 'type') and message.channel.type == disnake.ChannelType.forum:
        # 디버그 로그 - 포럼 메시지 감지
        print(f"[채팅] 포럼 채널 메시지 무시: 서버 {message.guild.id}, 채널 {message.channel.name}, 사용자 {message.author.name}")
        return
    
    # 포럼 쓰레드 내 메시지도 무시 (추가된 부분)
    if hasattr(message.channel, 'parent') and message.channel.parent and hasattr(message.channel.parent, 'type'):
        if message.channel.parent.type == disnake.ChannelType.forum:
            print(f"[채팅] 포럼 쓰레드 메시지 무시: 서버 {message.guild.id}, 채널 {message.channel.name}, 사용자 {message.author.name}")
            return

    # !list 명령어는 항상 허용 (auth.py에서 처리)
    if message.content.lower().startswith('!list'):
        return

    # !테놀 명령어 처리 추가
    if message.content.lower().startswith('!테놀 '):
        # 검색어 추출
        search_query = message.content[4:].strip()
        if not search_query:
            await message.reply("검색어를 입력하는 것이다! 예: `!테놀 고양이`")
            return
            
        # 서버 인증 확인
        from commands.auth import is_guild_authorized
        if not is_guild_authorized(message.guild.id):
            await message.reply("❌ 이 서버에서는 이 명령어를 사용할 수 없는 것이다.")
            return
        
        # tenor.py의 함수 호출
        from commands.tenor import process_tenor_command
        try:
            await process_tenor_command(message, search_query, is_slash_command=False)
        except Exception as e:
            print(f"!테놀 명령어 처리 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            await message.reply(f"❌ GIF 검색 중 오류가 발생한 것이다: {str(e)}")
        return

    # !집계 명령어 처리 추가
    if message.content.strip().lower() == "!집계":
        # 관리자 권한 확인
        if not message.author.guild_permissions.administrator:
            await message.channel.send("❌ 관리자만 사용할 수 있는 명령어인 것이다.")
            return
        
        # 집계 명령어 실행
        await process_text_aggregate_command(message)
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
        # 서버 데이터가 메모리에 없으면 DB에서 로드 시도 (추가된 부분)
        if db.is_mongo_connected():
            try:
                guild_chat_counts = db.get_guild_chat_counts(guild_id)
                if guild_chat_counts:
                    server_chat_counts[guild_id] = Counter(guild_chat_counts)
                    print(f"[on_message] 서버 {guild_id}의 채팅 카운트 로드: {len(guild_chat_counts)}개 항목")
                else:
                    server_chat_counts[guild_id] = Counter()
                    print(f"[on_message] 서버 {guild_id}에 채팅 데이터 없음, 새 카운터 생성")
            except Exception as e:
                print(f"[on_message] 서버 {guild_id} 채팅 카운트 로드 실패: {e}")
                server_chat_counts[guild_id] = Counter()
        else:
            server_chat_counts[guild_id] = Counter()

    excluded_roles = server_excluded_roles.get(guild_id, [])
    if any(role.id in excluded_roles for role in message.author.roles):
        return

    # 채팅 카운트 증가
    server_chat_counts[guild_id][user_id] += 1

    # MongoDB에만 저장 (로깅 추가)
    if db.is_mongo_connected():
        count = server_chat_counts[guild_id][user_id]
        save_result = db.save_chat_count(guild_id, user_id, count)

        # 100의 배수마다 로그 출력 (너무 많은 로그 방지)
        if count % 100 == 0:
            print(f"[채팅] 서버 {guild_id}, 사용자 {user_id}의 채팅 카운트: {count}회")

        # 메시지도 MongoDB에 저장
        db.save_message(guild_id, user_id, message.id, message.created_at)
    else:
        print("⚠️ MongoDB에 연결되지 않아 데이터를 저장할 수 없습니다")

# !집계 명령어를 처리하는 함수 수정
async def process_text_aggregate_command(message):
    """텍스트 명령어 !집계를 처리합니다. 현재 리더보드에 있는 채팅 데이터를 기준으로 집계합니다."""
    guild_id = message.guild.id
    
    # 원본 메시지 삭제 (추가된 부분)
    try:
        await message.delete()
    except Exception as e:
        print(f"집계 명령어 메시지 삭제 오류 (E001): {e}")
    
    # 진행 상황 메시지 전송
    progress_msg = await message.channel.send("집계를 시작하는 것이다... ⏳")
    
    try:
        # 서버 채팅 카운트 데이터 확인
        if guild_id not in server_chat_counts or not server_chat_counts[guild_id]:
            # 데이터가 없으면 DB에서 로드 시도
            if db.is_mongo_connected():
                guild_chat_counts = db.get_guild_chat_counts(guild_id)
                if guild_chat_counts:
                    server_chat_counts[guild_id] = Counter(guild_chat_counts)
                    print(f"[!집계] 서버 {guild_id}의 채팅 카운트 로드: {len(guild_chat_counts)}개 항목")
                else:
                    await progress_msg.edit(content="❌ 채팅 기록이 없어 집계할 수 없는 것이다. (E002)")
                    return
            else:
                await progress_msg.edit(content="❌ 데이터베이스에 연결되어 있지 않은 것이다. (E003)")
                return
                
        # 채팅 데이터 확인
        if not server_chat_counts[guild_id]:
            await progress_msg.edit(content="❌ 집계할 채팅 데이터가 없는 것이다. (E004)")
            return
            
        # 현재 상위 6명의 채팅 데이터 생성
        await progress_msg.edit(content="현재 리더보드의 채팅 데이터를 집계하는 것이다... ⏳")
            
        # 리더보드의 데이터를 사용하여 직접 집계 처리
        try:
            # 역할 설정 확인
            if guild_id not in server_roles:
                if db.is_mongo_connected():
                    role_data = db.get_guild_role_data(guild_id)
                    if role_data:
                        server_roles[guild_id] = role_data
                    else:
                        await progress_msg.edit(content="❌ 역할이 설정되지 않았습니다. `/역할설정` 명령어를 사용하는 것이다. (E005)")
                        return
                else:
                    await progress_msg.edit(content="❌ 역할 설정을 확인할 수 없는 것이다. (E006)")
                    return
            
            # 역할 객체 가져오기
            first_role = disnake.utils.get(message.guild.roles, id=server_roles[guild_id]["first"])
            other_role = disnake.utils.get(message.guild.roles, id=server_roles[guild_id]["other"])
            
            if not first_role or not other_role:
                await progress_msg.edit(content="❌ 설정된 역할을 찾을 수 없는 것이다. (E007)")
                return
                
            # 제외 역할 적용
            excluded_roles = server_excluded_roles.get(guild_id, [])
            excluded_members = {member.id for member in message.guild.members
                              if any(role.id in excluded_roles for role in member.roles)}
            
            # 채팅 카운트에서 상위 6명 가져오기
            chat_counts = server_chat_counts[guild_id]
            top_chatters = [(user_id, count) for user_id, count in chat_counts.most_common()
                          if user_id not in excluded_members][:6]
                          
            # 아무도 없으면 에러 메시지
            if not top_chatters:
                await progress_msg.edit(content="❌ 집계할 수 있는 사용자가 없는 것이다. (E008)")
                return
                
            await progress_msg.edit(content="역할을 배분하는 것이다... ⏳")
                
            # 1. 기존 역할 제거
            try:
                for member in message.guild.members:
                    if first_role in member.roles or other_role in member.roles:
                        await member.remove_roles(first_role, other_role)
            except disnake.Forbidden:
                await progress_msg.edit(content="❌ 역할을 제거할 권한이 없는 것이다. (E009)")
                return
            except Exception as e:
                await progress_msg.edit(content=f"❌ 역할 제거 중 오류: {e} (E010)")
                return
            
            # 2. 1등 역할 원래 색상으로 복원
            try:
                from commands.role_color import restore_role_original_color
                original_color = restore_role_original_color(message.guild, first_role)
                if original_color:
                    await first_role.edit(color=disnake.Color(original_color))
            except disnake.Forbidden:
                await progress_msg.edit(content="❌ 역할 색상을 변경할 권한이 없는 것이다! (E011)")
                return
            except Exception as e:
                await progress_msg.edit(content=f"❌ 역할 색상 변경 중 오류: {e} (E012)")
                return
            
            # 3. 새 역할 부여
            try:
                for index, (user_id, _) in enumerate(top_chatters):
                    member = message.guild.get_member(user_id)
                    if member:
                        if index == 0:  # 1등만
                            await member.add_roles(first_role)
                            role_type = "first"
                        else:  # 2-6등
                            await member.add_roles(other_role)
                            role_type = "other"
                        update_role_streak(guild_id, user_id, role_type)
            except disnake.Forbidden:
                await progress_msg.edit(content="❌ 역할을 부여할 권한이 없는 것이다! (E013)")
                return
            except Exception as e:
                await progress_msg.edit(content=f"❌ 역할 부여 중 오류: {e} (E014)")
                return
            
            # 4. 이미지 생성 및 전송
            await progress_msg.edit(content="결과 이미지를 생성 중인 것이다... ⏳")
            
            # 시작날짜와 종료날짜는 현재 시간으로 (의미 없음)
            import pytz  # 이 줄도 추가하면 더 안전함
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)
            
            # 이미지 생성 (aggregate.py의 함수 호출)
            try:
                from commands.aggregate import create_ranking_image
                image = await create_ranking_image(
                    message.guild,
                    top_chatters,
                    first_role,
                    other_role,
                    start_date=now,  # 현재 시간
                    end_date=now     # 현재 시간
                )
            except Exception as e:
                await progress_msg.edit(content=f"❌ 이미지 생성 중 오류: {e} (E015)")
                return
            
            if image:
                # 이미지 전송
                try:
                    await progress_msg.delete()  # 기존 메시지 삭제
                except:
                    pass  # 실패해도 계속 진행
                
                # 새 메시지로 이미지만 전송 (성공 메시지 제거)
                await message.channel.send(
                    file=disnake.File(fp=image, filename="ranking.png")
                )
                
                # 채팅 카운트 초기화
                reset_chat_counts(guild_id)
                
                # 마지막 집계 시간 저장
                save_last_aggregate_date(guild_id)
                
            else:
                await progress_msg.edit(content="❌ 이미지 생성에 실패한 것이다... (E016)")
                
        except Exception as e:
            print(f"!집계 명령어 처리 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            await progress_msg.edit(content=f"❌ 집계 중 오류가 발생한 것이다: {str(e)} (E017)")
            
    except Exception as e:
        print(f"!집계 명령어 처리 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        await progress_msg.edit(content=f"❌ 집계 명령어 처리 중 오류가 발생한 것이다: {str(e)} (E018)")

# 에러 핸들링 이벤트 추가
@bot.event
async def on_slash_command_error(inter, error):
    import traceback
    print(f"명령어 오류 발생 ({inter.data.name}): {error}")
    traceback.print.exc()

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
    print("❌ 토큰을 찾을 수 없는 것이다! .env 파일을 확인하는 것이다!")