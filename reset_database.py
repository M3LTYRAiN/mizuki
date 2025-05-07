import sqlite3

def reset_database():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()

    # 테이블 삭제
    c.execute("DROP TABLE IF EXISTS roles")
    c.execute("DROP TABLE IF EXISTS excluded_roles")
    c.execute("DROP TABLE IF EXISTS chat_counts")
    c.execute("DROP TABLE IF EXISTS messages")
    c.execute("DROP TABLE IF EXISTS aggregate_dates")
    c.execute("DROP TABLE IF EXISTS role_streaks")

    # 테이블 재생성
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
    c.execute('''CREATE TABLE IF NOT EXISTS role_streaks (
                    guild_id INTEGER,
                    user_id INTEGER,
                    role_type TEXT,
                    streak_count INTEGER,
                    last_updated DATETIME,
                    PRIMARY KEY (guild_id, user_id)
                )''')

    conn.commit()
    conn.close()
    print("Database has been reset.")

if __name__ == "__main__":
    reset_database()
