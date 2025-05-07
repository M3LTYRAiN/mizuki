import asyncio
import disnake
from disnake.ext import commands, tasks
from collections import Counter
import sqlite3
import datetime  # Add this import for date handling
from dotenv import load_dotenv  # 추가
import os  # 추가

# MacOS에서 이벤트 루프 정책을 설정 (Python 3.13 충돌 해결)
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

# Bot 설정 (최소한의 설정으로 변경)
bot = commands.InteractionBot(
    intents=intents,
    test_guilds=None  # 전역 명령어로 설정
)

server_roles = {}
server_chat_counts = {}
server_excluded_roles = {}
last_aggregate_dates = {}
role_streaks = {}
level_roles = {}  # 추가: 레벨별 역할을 저장할 변수

# Database connection - 상대 경로에서 절대 경로로 변경
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bot_data.db')
print(f"데이터베이스 경로: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Create tables if they don't exist
c.execute('''CREATE TABLE IF NOT EXISTS roles (
                guild_id INTEGER PRIMARY KEY,
                first_role_id INTEGER,
                other_role_id INTEGER
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS excluded_roles (
                guild_id INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, role_id)
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS chat_counts (
                guild_id INTEGER,
                user_id INTEGER,
                count INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS messages (
                guild_id INTEGER,
                user_id INTEGER,
                message_id INTEGER,
                timestamp DATETIME,
                PRIMARY KEY (guild_id, user_id, message_id)
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS aggregate_dates (
                guild_id INTEGER PRIMARY KEY,
                last_aggregate_date DATETIME
            )''')

# role_streaks 테이블은 이미 존재하면 유지, 없을 때만 생성
c.execute('''CREATE TABLE IF NOT EXISTS role_streaks (
                guild_id INTEGER,
                user_id INTEGER,
                role_type TEXT,
                streak_count INTEGER DEFAULT 1,
                PRIMARY KEY (guild_id, user_id)
            )''')

# 테이블 생성 부분에 level_roles 테이블 추가
c.execute('''CREATE TABLE IF NOT EXISTS level_roles (
                guild_id INTEGER,
                level INTEGER,
                role_id INTEGER,
                PRIMARY KEY (guild_id, level)
            )''')

# 테이블 생성 부분에 user_card_settings 테이블 추가
c.execute('''CREATE TABLE IF NOT EXISTS user_card_settings (
                guild_id INTEGER,
                user_id INTEGER,
                bg_color_top TEXT DEFAULT '#9BBAFF',
                bg_color_bottom TEXT DEFAULT '#AAB5F5',
                card_style TEXT DEFAULT 'default',
                last_updated DATETIME,
                PRIMARY KEY (guild_id, user_id)
            )''')

# 테이블 생성 부분에 인증 관련 테이블 추가
c.execute('''CREATE TABLE IF NOT EXISTS auth_codes (
                code TEXT PRIMARY KEY,
                created_at DATETIME,
                used INTEGER DEFAULT 0,
                used_by INTEGER DEFAULT NULL
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS authorized_guilds (
                guild_id INTEGER PRIMARY KEY,
                authorized_at DATETIME,
                auth_code TEXT
            )''')

conn.commit()

# Load role data from database
def load_role_data():
    global server_roles
    c.execute("SELECT guild_id, first_role_id, other_role_id FROM roles")
    rows = c.fetchall()
    for row in rows:
        guild_id, first_role_id, other_role_id = row
        server_roles[guild_id] = {"first": first_role_id, "other": other_role_id}
    print("Role data loaded successfully:", server_roles)  # Add this line for debugging

# Save role data to database
def save_role_data(guild_id, first_role_id, other_role_id):
    c.execute("REPLACE INTO roles (guild_id, first_role_id, other_role_id) VALUES (?, ?, ?)",
              (guild_id, first_role_id, other_role_id))
    conn.commit()
    print("Role data saved successfully:", {"guild_id": guild_id, "first_role_id": first_role_id, "other_role_id": other_role_id})  # Add this line for debugging

# Load excluded role data from database
def load_excluded_role_data():
    global server_excluded_roles
    c.execute("SELECT guild_id, role_id FROM excluded_roles")
    rows = c.fetchall()
    for row in rows:
        guild_id, role_id = row
        if guild_id not in server_excluded_roles:
            server_excluded_roles[guild_id] = []
        server_excluded_roles[guild_id].append(role_id)
    print("Excluded role data loaded successfully:", server_excluded_roles)  # Add this line for debugging

# Save excluded role data to database
def save_excluded_role_data(guild_id, excluded_roles):
    c.execute("DELETE FROM excluded_roles WHERE guild_id = ?", (guild_id,))
    for role_id in excluded_roles:
        c.execute("INSERT INTO excluded_roles (guild_id, role_id) VALUES (?, ?)", (guild_id, role_id))
    conn.commit()
    print("Excluded role data saved successfully:", {"guild_id": guild_id, "excluded_roles": excluded_roles})  # Add this line for debugging

# Load chat counts from database
def load_chat_counts():
    global server_chat_counts
    c.execute("SELECT guild_id, user_id, count FROM chat_counts")
    rows = c.fetchall()
    for row in rows:
        guild_id, user_id, count = row
        if guild_id not in server_chat_counts:
            server_chat_counts[guild_id] = Counter()
        server_chat_counts[guild_id][user_id] = count
    print("Chat counts loaded successfully:", server_chat_counts)  # Add this line for debugging

# Save chat counts to database
def save_chat_counts():
    for guild_id, counts in server_chat_counts.items():
        for user_id, count in counts.items():
            c.execute("REPLACE INTO chat_counts (guild_id, user_id, count) VALUES (?, ?, ?)",
                      (guild_id, user_id, count))
    conn.commit()
    # print("Chat counts saved successfully")  # Remove this line to stop printing

# Reset chat counts for a guild
def reset_chat_counts(guild_id):
    if guild_id in server_chat_counts:
        server_chat_counts[guild_id].clear()  # Counter 객체 초기화
        # 데이터베이스에서도 해당 길드의 모든 채팅 카운트 삭제
        c.execute("DELETE FROM chat_counts WHERE guild_id = ?", (guild_id,))
        conn.commit()
    print(f"Chat counts reset for guild {guild_id}")

# Save last aggregate date to database
def save_last_aggregate_date(guild_id):
    last_aggregate_date = datetime.datetime.utcnow()
    # 저장할 때는 마이크로초를 제외하고 저장
    formatted_date = last_aggregate_date.strftime("%Y-%m-%d %H:%M:%S")
    # 수정: 2개의 컬럼에 2개의 값만 전달
    c.execute("REPLACE INTO aggregate_dates (guild_id, last_aggregate_date) VALUES (?, ?)",
              (guild_id, formatted_date))
    conn.commit()
    last_aggregate_dates[guild_id] = last_aggregate_date
    print(f"Last aggregate date saved for guild {guild_id}: {formatted_date}")

# Get last aggregate date from database
def get_last_aggregate_date(guild_id):
    if guild_id in last_aggregate_dates:
        return last_aggregate_dates[guild_id]
    c.execute("SELECT last_aggregate_date FROM aggregate_dates WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    if row:
        try:
            # 마이크로초가 포함된 경우도 처리할 수 있도록 수정
            timestamp = row[0].split('.')[0]  # 마이크로초 부분 제거
            last_aggregate_date = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            last_aggregate_dates[guild_id] = last_aggregate_date
            return last_aggregate_date
        except (ValueError, AttributeError) as e:
            print(f"Error parsing date: {row[0]}, Error: {e}")
            return None
    return None

# Get messages in a specific period from database
def get_messages_in_period(guild_id, start_date, end_date):
    c.execute("SELECT user_id FROM messages WHERE guild_id = ? AND timestamp BETWEEN ? AND ?", (guild_id, start_date, end_date))
    rows = c.fetchall()
    return [{"user_id": row[0]} for row in rows]

# Delete old messages from database
@tasks.loop(hours=24)
async def delete_old_messages():
    cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=30)  # Change 30 to desired number of days
    c.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_date,))
    conn.commit()
    print("Old messages deleted successfully")  # Add this line for debugging

# 연속 기록 로드 함수 추가
def load_role_streaks():
    global role_streaks
    c.execute("""
        SELECT guild_id, user_id, role_type, streak_count 
        FROM role_streaks
    """)
    rows = c.fetchall()
    streak_data = {}
    for guild_id, user_id, role_type, streak_count in rows:
        if guild_id not in streak_data:
            streak_data[guild_id] = {}
        streak_data[guild_id][user_id] = {"type": role_type, "count": streak_count}
    print(f"Loaded {len(rows)} role streaks:", streak_data)  # 디버깅 메시지 개선
    return streak_data

# 역할-레벨 데이터 로드 함수 추가
def load_level_roles():
    global level_roles
    c.execute("SELECT guild_id, level, role_id FROM level_roles")
    rows = c.fetchall()
    for row in rows:
        guild_id, level, role_id = row
        if guild_id not in level_roles:
            level_roles[guild_id] = {}
        level_roles[guild_id][level] = role_id
    print(f"Level roles loaded: {level_roles}")

# 디버그 정보 추가 - 사용자 카드 설정 확인
@bot.event
async def on_ready():
    global role_streaks
    try:
        print(f"Logged in as {bot.user.name}")
        print(f"Bot ID: {bot.user.id}")
        print(f"데이터베이스 경로: {DB_PATH}")
        
        # 봇 상태 메시지 설정 - "通りゃんせ　通りゃんせ" 게임 하는 중으로 표시
        game_activity = disnake.Game(name="通りゃんせ　通りゃんせ")
        await bot.change_presence(activity=game_activity)
        
        # 데이터 로드
        load_role_data()
        load_excluded_role_data()
        load_chat_counts()
        role_streaks = load_role_streaks()
        load_level_roles()  # 레벨 역할 로드
        
        # 데이터베이스에 카드 설정 테이블이 있는지 확인
        c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='user_card_settings'")
        has_table = c.fetchone()[0] > 0
        print(f"카드 설정 테이블 존재 여부: {has_table}")
        
        # 샘플 카드 설정 확인 (디버깅용)
        if has_table:
            c.execute("SELECT COUNT(*) FROM user_card_settings")
            count = c.fetchone()[0]
            print(f"저장된 카드 설정 수: {count}")
        
        print(f"✅ 봇이 준비되었습니다! (핑: {round(bot.latency * 1000)}ms)")
        
    except Exception as e:
        print(f"Error in on_ready: {e}")

def get_role_streak(guild_id, user_id):
    # 먼저 데이터베이스에서 확인 (캐시보다 데이터베이스 우선)
    c.execute("""
        SELECT role_type, streak_count 
        FROM role_streaks 
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id))
    
    row = c.fetchone()
    result = {"type": row[0], "count": row[1]} if row else {"type": None, "count": 0}
    
    # 메모리 캐시 업데이트
    if guild_id not in role_streaks:
        role_streaks[guild_id] = {}
    role_streaks[guild_id][user_id] = result
    
    return result

def update_role_streak(guild_id, user_id, role_type):
    try:
        # 1. 먼저 해당 유저의 현재 기록 조회
        c.execute("""
            SELECT role_type, streak_count 
            FROM role_streaks 
            WHERE guild_id = ? AND user_id = ?
        """, (guild_id, user_id))
        
        current_record = c.fetchone()
        
        # 2. 새로운 streak 계산
        if current_record and current_record[0] == role_type:
            new_streak = current_record[1] + 1
        else:
            new_streak = 1  # 새로운 역할이거나 기존 기록이 없으면 1부터 시작
        
        # 3. 개별 유저의 기록 업데이트
        c.execute("""
            INSERT OR REPLACE INTO role_streaks 
            (guild_id, user_id, role_type, streak_count) 
            VALUES (?, ?, ?, ?)
        """, (guild_id, user_id, role_type, new_streak))
        
        # 4. 메모리 캐시 업데이트
        if guild_id not in role_streaks:
            role_streaks[guild_id] = {}
        role_streaks[guild_id][user_id] = {
            "type": role_type,
            "count": new_streak
        }
        
        conn.commit()
        print(f"Updated streak for user {user_id} in guild {guild_id}: {new_streak} ({role_type})")
        return new_streak
        
    except Exception as e:
        print(f"Error updating streak: {e}")
        conn.rollback()
        return 1  # 에러 발생 시 1 반환

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

    # 기존 메시지 처리 로직
    guild_id = message.guild.id
    user_id = message.author.id
    
    if guild_id not in server_chat_counts:
        server_chat_counts[guild_id] = Counter()

    excluded_roles = server_excluded_roles.get(guild_id, [])
    if any(role.id in excluded_roles for role in message.author.roles):
        return

    # 채팅 카운트 증가
    server_chat_counts[guild_id][user_id] += 1
    save_chat_counts()  # 데이터베이스에 채팅 카운트 저장

    # 레벨 업데이트 (새로 추가된 부분)
    try:
        from commands.level import update_user_level, get_user_level_info
        is_level_up = update_user_level(guild_id, user_id)
        
        # 레벨업 알림 (선택사항)
        if is_level_up:
            level_info = get_user_level_info(guild_id, user_id)
            await message.channel.send(
                f" {message.author.mention}님이 레벨 {level_info['level']}이 된 것이다!"
            )
    except Exception as e:
        print(f"Error updating level: {e}")

    # 메시지 저장
    c.execute("INSERT INTO messages (guild_id, user_id, message_id, timestamp) VALUES (?, ?, ?, ?)",
              (guild_id, user_id, message.id, message.created_at))
    conn.commit()

# 역할-레벨 데이터 저장을 위한 함수 추가
def save_level_role(guild_id, level, role_id):
    """레벨별 역할 설정을 데이터베이스에 저장하는 것이다."""
    c.execute("""
        INSERT OR REPLACE INTO level_roles 
        (guild_id, level, role_id) 
        VALUES (?, ?, ?)
    """, (guild_id, level, role_id))
    conn.commit()
    
    # 메모리 캐시 업데이트
    if 'level_roles' not in globals():
        global level_roles
        level_roles = {}
    
    if guild_id not in level_roles:
        level_roles[guild_id] = {}
    
    level_roles[guild_id][level] = role_id
    print(f"Level role saved: guild={guild_id}, level={level}, role={role_id}")

# 사용자별 레벨 카드 설정 로드 함수
def get_user_card_settings(guild_id, user_id):
    """사용자별 레벨 카드 설정을 가져오는 것이다."""
    c.execute("""
        SELECT bg_color_top, bg_color_bottom, card_style
        FROM user_card_settings
        WHERE guild_id = ? AND user_id = ?
    """, (guild_id, user_id))
    
    row = c.fetchone()
    
    if row:
        return {
            "bg_color_top": row[0],
            "bg_color_bottom": row[1],
            "card_style": row[2]
        }
    else:
        # 기본 설정 반환
        return {
            "bg_color_top": "#9BBAFF",  # 기본 상단 색상 (연한 하늘색)
            "bg_color_bottom": "#AAB5F5",  # 기본 하단 색상 (연한 보라색)
            "card_style": "default"
        }

# 사용자별 레벨 카드 설정 업데이트 함수
def update_user_card_settings(guild_id, user_id, settings):
    """사용자별 레벨 카드 설정을 업데이트하는 것이다."""
    c.execute("""
        INSERT OR REPLACE INTO user_card_settings 
        (guild_id, user_id, bg_color_top, bg_color_bottom, card_style, last_updated)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        guild_id,
        user_id,
        settings.get("bg_color_top", "#9BBAFF"),
        settings.get("bg_color_bottom", "#AAB5F5"),
        settings.get("card_style", "default")
    ))
    conn.commit()
    
    print(f"Updated card settings for user {user_id} in guild {guild_id}")
    return True

# 봇 실행 (환경 변수에서 토큰 가져오기)
TOKEN = os.getenv('DISCORD_TOKEN')  # 'DISCORD_TOKEN'을 매개변수로 추가

# Import commands after all definitions
import commands.role_set
import commands.role_exclude
import commands.leaderboard
import commands.aggregate
import commands.reset_streak
import commands.level
import commands.level_role
import commands.card_settings
import commands.omikuji
import commands.role_color
import commands.auth  # 인증 시스템 모듈
import commands.manual  # 메뉴얼 명령어 추가
import commands.tenor

# 토큰 디버깅
if TOKEN:
    masked_token = TOKEN[:4] + '*' * (len(TOKEN) - 8) + TOKEN[-4:]
    print(f"토큰 로드 성공: {masked_token}")
    # 봇 실행 코드 추가
    bot.run(TOKEN)
else:
    print("❌ 토큰을 찾을 수 없는 것이다! .env 파일을 확인하는 것이다.")