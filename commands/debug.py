import disnake
from disnake.ext import commands
from bot import bot, server_roles, server_excluded_roles
import database as db
import json

@bot.slash_command(name="디버그", description="역할 설정 데이터를 확인하는 것이다.")
@commands.has_permissions(administrator=True)
async def 디버그(inter: disnake.ApplicationCommandInteraction):
    guild_id = inter.guild.id
    await inter.response.defer(ephemeral=True)
    
    debug_info = []
    debug_info.append(f"서버 ID: {guild_id}")
    
    # 1. 메모리 상태 확인
    if guild_id in server_roles:
        debug_info.append(f"메모리에 역할 설정 존재: {server_roles[guild_id]}")
    else:
        debug_info.append("메모리에 역할 설정 없음")
    
    # 2. MongoDB 직접 확인
    if db.is_mongo_connected():
        debug_info.append("MongoDB 연결됨")
        
        # 문자열과 정수 모두 확인
        try:
            # 정수형으로 찾기
            doc1 = db.roles_collection.find_one({"guild_id": guild_id})
            if doc1:
                debug_info.append(f"정수 guild_id로 역할 찾음: {doc1}")
            else:
                debug_info.append("정수 guild_id로 역할 못찾음")
                
            # 문자열로 찾기
            doc2 = db.roles_collection.find_one({"guild_id": str(guild_id)})
            if doc2:
                debug_info.append(f"문자열 guild_id로 역할 찾음: {doc2}")
            else:
                debug_info.append("문자열 guild_id로 역할 못찾음")
                
            # 전체 데이터베이스 검색
            debug_info.append("\n모든 역할 데이터 확인:")
            cursor = db.roles_collection.find({})
            for doc in cursor:
                debug_info.append(f"- guild_id: {doc.get('guild_id')} (타입: {type(doc.get('guild_id')).__name__}), 역할: {doc}")
        except Exception as e:
            debug_info.append(f"MongoDB 조회 오류: {e}")
    else:
        debug_info.append("MongoDB 연결 안됨")
    
    info_text = "\n".join(debug_info)
    await inter.followup.send(f"**디버그 정보**\n```\n{info_text}\n```", ephemeral=True)

    # 수동으로 다시 로드 시도
    try:
        role_data = db.get_guild_role_data(guild_id)
        if role_data:
            server_roles[guild_id] = role_data
            await inter.followup.send(f"✅ 역할 데이터 다시 로드 성공: {role_data}", ephemeral=True)
        else:
            await inter.followup.send("❌ DB에서 역할 데이터를 찾을 수 없습니다", ephemeral=True)
    except Exception as e:
        await inter.followup.send(f"❌ 역할 데이터 로드 중 오류: {e}", ephemeral=True)
