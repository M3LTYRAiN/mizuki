from disnake.ext import commands
import disnake
from bot import bot, server_roles
import database as db

@bot.slash_command(name="역할설정", description="서버에서 사용할 역할을 설정하는 것이다.")
@commands.has_permissions(administrator=True)
async def 역할설정(inter: disnake.ApplicationCommandInteraction, first_role: disnake.Role, other_role: disnake.Role):
    server_roles[inter.guild.id] = {"first": first_role.id, "other": other_role.id}
    await inter.response.send_message(f"✅ 역할 설정 완료: {first_role.name} (1위), {other_role.name} (2~6위)", ephemeral=True)
    
    # MongoDB에 저장
    if db.is_mongo_connected():
        db.save_role_data(inter.guild.id, first_role.id, other_role.id)
        print(f"역할 설정 데이터가 MongoDB에 저장됨: {inter.guild.id}, {first_role.id}, {other_role.id}")
    else:
        print("⚠️ MongoDB에 연결되지 않아 역할 데이터를 저장할 수 없습니다")
