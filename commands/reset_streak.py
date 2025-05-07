from disnake.ext import commands
import disnake
from bot import bot, conn, c, role_streaks

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
                # 서버의 모든 멤버의 연속 기록을 0으로 설정
                for member in inter.guild.members:
                    # 데이터베이스에서 해당 사용자의 streak_count만 0으로 초기화
                    c.execute("""
                        UPDATE role_streaks 
                        SET streak_count = 0 
                        WHERE guild_id = ? AND user_id = ?
                    """, (guild_id, member.id))
                    
                    # 메모리에서도 연속 기록 0으로 초기화
                    if guild_id in role_streaks and member.id in role_streaks[guild_id]:
                        role_streaks[guild_id][member.id]["count"] = 0

                conn.commit()
                print(f"Reset all member streaks to 0 for guild {guild_id}")  # 디버깅용
                await interaction.response.edit_message(content="✅ 모든 사용자의 연속 기록이 0으로 초기화된 것이다.", view=None)
            except Exception as e:
                print(f"Error resetting streaks: {e}")
                await interaction.response.edit_message(content="❌ 초기화 중 오류가 발생한 것이다.", view=None)
            self.stop()

        @disnake.ui.button(label="취소", style=disnake.ButtonStyle.secondary)
        async def cancel_button(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
            await interaction.response.edit_message(content="❌ 연속 기록 초기화가 취소된 것이다.", view=None)
            self.stop()

    view = ConfirmView()
    await inter.response.send_message("⚠️ 정말로 모든 사용자의 연속 기록을 0으로 초기화하는 것이냐?", view=view)
