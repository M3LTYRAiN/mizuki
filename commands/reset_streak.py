from disnake.ext import commands
import disnake
from bot import bot, role_streaks
import database as db

@bot.slash_command(name="연속초기화", description="서버의 모든 연속 기록을 초기화하는 것이다.")
@commands.has_permissions(administrator=True)
async def 연속초기화(inter: disnake.ApplicationCommandInteraction):
    guild_id = inter.guild.id

    class ConfirmView(disnake.ui.View):
        def __init__(self):
            super().__init__(timeout=30.0)

        @disnake.ui.button(label="확인", style=disnake.ButtonStyle.danger)
        async def confirm_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            try:
                if not db.is_mongo_connected():
                    await interaction.response.edit_message(
                        content="❌ MongoDB에 연결되어 있지 않습니다. 연속 기록을 초기화할 수 없습니다.", 
                        view=None
                    )
                    self.stop()
                    return
                
                # MongoDB에서 해당 서버의 모든 연속 기록 초기화
                result = db.reset_role_streaks(guild_id)
                
                # 메모리에서도 연속 기록 초기화
                if guild_id in role_streaks:
                    for user_id in role_streaks[guild_id]:
                        role_streaks[guild_id][user_id]["count"] = 0

                print(f"Reset all member streaks to 0 for guild {guild_id}, affected {result} records")
                await interaction.response.edit_message(content="✅ 모든 사용자의 연속 기록이 0으로 초기화된 것이다.", view=None)
            except Exception as e:
                print(f"연속 기록 초기화 중 오류: {e}")
                await interaction.response.edit_message(content=f"❌ 초기화 중 오류가 발생한 것이다: {e}", view=None)
            self.stop()

        @disnake.ui.button(label="취소", style=disnake.ButtonStyle.secondary)
        async def cancel_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            await interaction.response.edit_message(content="❌ 연속 기록 초기화가 취소된 것이다.", view=None)
            self.stop()

    view = ConfirmView()
    await inter.response.send_message("⚠️ 정말로 모든 사용자의 연속 기록을 0으로 초기화하는 것이냐?", view=view)
