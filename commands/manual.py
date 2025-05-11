from disnake.ext import commands
import disnake
from bot import bot, server_roles, server_excluded_roles, server_chat_counts
import database as db
import os
import pytz
from datetime import datetime

@bot.slash_command(name="메뉴얼", description="미즈키 사용 설명서를 보여주는 것이다.")
async def 메뉴얼(inter: disnake.ApplicationCommandInteraction):
    # 기본 임베드 생성
    embed = disnake.Embed(
        title="미즈키 사용 설명서",
        description="서버의 채팅을 집계하여 역할을 부여하는 봇인 것이다!",
        color=disnake.Color.blue()
    )
    
    # 메뉴얼 내용 설정
    embed.add_field(
        name="🔍 기본 기능",
        value=(
            "이 봇은 서버 내 사용자들의 채팅을 집계하는 것이다!\n"
            "**`/집계`** 명령어를 통해 가장 많이 채팅한 6명에게 역할을 부여하는 것이다!\n"
            "1위 사용자는 특별한 역할을 받게 되는 것이다!\n"
            "연속으로 순위권에 들면 연속 집계 횟수도 표시되는 것이다!"
        ),
        inline=False
    )
    
    # 관리자 명령어 설명
    embed.add_field(
        name="⚙️ 관리자 명령어",
        value=(
            "`/역할설정` - 1위와 2~6위에게 부여할 역할을 설정하는 것이다!\n"
            "`/역할제외` - 집계에서 제외할 역할을 설정하는 것이다!\n"
            "`/집계` - 특정 기간의 채팅을 집계하여 역할을 부여하는 것이다!\n"
            "  → 형식: YYYYMMDD (예: 20230101) 또는 't'(오늘)\n"
            "`/역할색상` - 1위 역할의 색상을 변경하는 것이다!\n"
            "`/연속초기화` - 특정 사용자의 연속 집계 기록을 초기화하는 것이다!\n"
        ),
        inline=False
    )
    
    # 일반 명령어 설명
    embed.add_field(
        name="📋 일반 명령어",
        value=(
            "`/리더보드` - 채팅 순위를 보여주는 것이다!\n"
            "`/오미쿠지` - 오늘의 운세를 확인하는 것이다!\n"
            "`/tenor` - 테놀 GIF를 검색하는 것이다!\n"
            "`/메뉴얼` - 이 도움말을 보는 것이다!\n"
            "`/핑` - 봇의 응답 속도를 확인하는 것이다!"
        ),
        inline=False
    )
    
    # 집계 방식 설명
    embed.add_field(
        name="📊 집계 방식",
        value=(
            "1. 봇이 서버의 모든 채팅을 자동으로 집계하는 것이다!\n"
            "2. `/집계` 명령어로 특정 기간의 채팅량을 확인하는 것이다!\n"
            "3. 상위 6명의 사용자에게 역할이 부여되는 것이다!\n"
            "4. 1위는 특별한 역할을, 2~6위는 다른 역할을 받는 것이다!\n"
            "5. 역할은 `/역할설정` 명령어로 미리 지정해야 하는 것이다!\n"
            "6. 제외 역할을 가진 사용자는 집계에서 제외되는 것이다!"
        ),
        inline=False
    )
    
    # 푸터 추가
    embed.set_footer(text="더 궁금한 점이 있다면 관리자에게 문의하는 것이다!")
    
    # 버튼 뷰 생성
    class ManualView(disnake.ui.View):
        def __init__(self):
            super().__init__(timeout=300)  # 5분 타임아웃
            
        @disnake.ui.button(label="서버 정보", style=disnake.ButtonStyle.primary, emoji="🖥️")
        async def server_info(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
            # 응답 지연 설정 (중요: 처리 시간이 오래 걸릴 수 있으므로)
            await button_inter.response.defer(ephemeral=True)
            
            try:
                # 서버 정보 임베드 생성
                guild_id = button_inter.guild.id
                guild = button_inter.guild
                
                info_embed = disnake.Embed(
                    title=f"🖥️ {guild.name} 서버 정보",
                    description="이 서버에 대해 내가 알고 있는 정보인 것이다!",
                    color=disnake.Color.green()
                )
                
                # 서버 기본 정보 (모두 볼 수 있도록 추가)
                created_at_kst = guild.created_at.replace(tzinfo=datetime.timezone.utc).astimezone(pytz.timezone('Asia/Seoul'))
                info_embed.add_field(
                    name="📅 서버 생성일",
                    value=created_at_kst.strftime("%Y년 %m월 %d일"),
                    inline=True
                )
                
                # 서버 통계 정보
                total_members = len(guild.members)
                bot_count = sum(1 for member in guild.members if member.bot)
                human_count = total_members - bot_count
                
                stats = f"👥 총 멤버: {total_members}명\n" \
                       f"👤 사용자: {human_count}명\n" \
                       f"🤖 봇: {bot_count}개"
                
                info_embed.add_field(name="📊 서버 통계", value=stats, inline=True)
                
                # 채널 정보 추가
                text_channels = len(guild.text_channels)
                voice_channels = len(guild.voice_channels)
                categories = len(guild.categories)
                
                channels = f"💬 텍스트: {text_channels}개\n" \
                         f"🔊 음성: {voice_channels}개\n" \
                         f"📁 카테고리: {categories}개"
                         
                info_embed.add_field(name="채널 정보", value=channels, inline=True)
                
                # 역할 설정 정보 - 모든 사용자에게 역할 이름 표시, 관리자에게만 ID 표시
                role_info = "❌ 설정되지 않은 것이다! `/역할설정` 명령어로 설정하는 것이다!"
                if guild_id in server_roles:
                    first_role_id = server_roles[guild_id].get('first')
                    other_role_id = server_roles[guild_id].get('other')
                    
                    first_role = disnake.utils.get(guild.roles, id=first_role_id)
                    other_role = disnake.utils.get(guild.roles, id=other_role_id)
                    
                    if first_role and other_role:
                        if button_inter.author.guild_permissions.administrator:
                            # 관리자용 상세 정보
                            role_info = f"1위 역할: {first_role.mention} (ID: {first_role_id})\n" \
                                       f"2~6위 역할: {other_role.mention} (ID: {other_role_id})"
                        else:
                            # 일반 사용자용 정보 (ID 제외)
                            role_info = f"1위 역할: {first_role.mention}\n" \
                                       f"2~6위 역할: {other_role.mention}"
                
                info_embed.add_field(name="🏆 역할 설정", value=role_info, inline=False)
                
                # 제외 역할 정보 표시
                excluded_info = "❕ 설정된 제외 역할이 없는 것이다!"
                if guild_id in server_excluded_roles and server_excluded_roles[guild_id]:
                    excluded_roles = []
                    for role_id in server_excluded_roles[guild_id]:
                        role = disnake.utils.get(guild.roles, id=role_id)
                        if role:
                            if button_inter.author.guild_permissions.administrator:
                                # 관리자용 상세 정보
                                excluded_roles.append(f"• {role.mention} (ID: {role_id})")
                            else:
                                # 일반 사용자용 정보 (ID 제외)
                                excluded_roles.append(f"• {role.mention}")
                    
                    if excluded_roles:
                        excluded_info = "\n".join(excluded_roles)
                
                # 관리자가 아니면 제외 역할 정보를 더 간결하게 표시
                if button_inter.author.guild_permissions.administrator:
                    info_embed.add_field(name="🚫 제외 역할", value=excluded_info, inline=False)
                else:
                    # 역할이 많을 경우 일반 사용자에게는 축약 표시
                    if guild_id in server_excluded_roles and len(server_excluded_roles[guild_id]) > 10:
                        excluded_roles_count = len(server_excluded_roles[guild_id])
                        excluded_info += f"\n\n(총 {excluded_roles_count}개 역할이 제외됨)"
                    info_embed.add_field(name="🚫 제외 역할", value=excluded_info, inline=False)
                
                # 마지막 집계 날짜 정보 (모두에게 표시)
                last_aggregate = "❕ 아직 집계를 한 적이 없는 것이다!"
                if db.is_mongo_connected():
                    try:
                        last_date = db.get_last_aggregate_date(guild_id)
                        if last_date:
                            kst = pytz.timezone('Asia/Seoul')
                            last_date_kst = last_date.astimezone(kst)
                            last_aggregate = last_date_kst.strftime("%Y년 %m월 %d일 %H시 %M분")
                    except Exception as e:
                        last_aggregate = f"❌ 정보를 확인할 수 없는 것이다: {e}"
                
                info_embed.add_field(name="📅 마지막 집계 일시", value=last_aggregate, inline=False)
                
                # 채팅 기록 날짜 범위 조회 (모두에게 표시)
                chat_date_range = "기록 없음"
                if db.is_mongo_connected():
                    try:
                        # 데이터베이스 쿼리 최적화 - 인덱스 사용 및 필요한 필드만 조회
                        # 쿼리 수행 시간 제한 설정 (5초)
                        oldest_message = list(db.messages_collection.find(
                            {"guild_id": guild_id}, 
                            {"timestamp": 1, "_id": 0}  # _id 필드 제외
                        ).sort("timestamp", 1).limit(1).max_time_ms(5000))
                        
                        newest_message = list(db.messages_collection.find(
                            {"guild_id": guild_id}, 
                            {"timestamp": 1, "_id": 0}  # _id 필드 제외
                        ).sort("timestamp", -1).limit(1).max_time_ms(5000))
                        
                        # 날짜 범위가 있으면 포맷팅
                        if oldest_message and newest_message:
                            oldest_date = oldest_message[0].get("timestamp")
                            newest_date = newest_message[0].get("timestamp")
                            
                            oldest_kst = oldest_date.astimezone(pytz.timezone('Asia/Seoul'))
                            newest_kst = newest_date.astimezone(pytz.timezone('Asia/Seoul'))
                            
                            # 요청된 형식(yyyymmdd~yyyymmdd)으로 포맷팅
                            chat_date_range = f"{oldest_kst.strftime('%Y%m%d')}~{newest_kst.strftime('%Y%m%d')}"
                            
                            # 추가 정보로 가독성 있는 날짜도 표시
                            chat_date_range += f"\n({oldest_kst.strftime('%Y년 %m월 %d일')} ~ {newest_kst.strftime('%Y년 %m월 %d일')})"
                            
                            # 총 메시지 수 표시
                            total_messages = db.messages_collection.count_documents(
                                {"guild_id": guild_id},
                                limit=10000,  # 대략적인 숫자만 필요하므로 제한
                                maxTimeMS=3000  # 시간 제한 3초
                            )
                            # 숫자가 너무 크면 "10,000+" 형태로 표시
                            if total_messages >= 10000:
                                message_count_str = "10,000+"
                            else:
                                message_count_str = f"{total_messages:,}"
                            
                            chat_date_range += f"\n총 {message_count_str}개 메시지"
                    except Exception as e:
                        chat_date_range = f"정보 조회 실패: {type(e).__name__}"
                        print(f"채팅 기록 조회 오류: {e}")
                
                info_embed.add_field(
                    name="📊 채팅 기록 범위",
                    value=chat_date_range,
                    inline=False
                )
                
                # 현재 시간 표시
                kst_now = datetime.now(pytz.timezone('Asia/Seoul'))
                formatted_now = kst_now.strftime("%Y-%m-%d %H:%M:%S")
                info_embed.set_footer(text=f"정보 조회 시간: {formatted_now}")
                
                # 임베드에 서버 아이콘 추가
                if guild.icon:
                    info_embed.set_thumbnail(url=guild.icon.url)
                    
                # 서버 배너가 있으면 추가
                if guild.banner:
                    info_embed.set_image(url=guild.banner.url)
                
                # 응답 지연이 설정되어 있으므로 followup 메시지 사용
                await button_inter.followup.send(embed=info_embed, ephemeral=True)
                
            except Exception as e:
                # 오류 발생 시 간단한 메시지로 대체
                error_message = f"서버 정보를 불러오는 중 오류가 발생했습니다: {type(e).__name__}"
                print(f"서버 정보 버튼 오류: {e}")
                if not button_inter.response.is_done():
                    await button_inter.response.send_message(error_message, ephemeral=True)
                else:
                    await button_inter.followup.send(error_message, ephemeral=True)
    
    # 뷰와 함께 메뉴얼 전송
    await inter.response.send_message(embed=embed, view=ManualView())