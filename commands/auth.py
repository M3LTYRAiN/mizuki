import disnake
from disnake.ext import commands
import random
import string
import datetime
import asyncio
from bot import bot  # SQLite 관련 conn, c 임포트 제거
import database as db

# 서버 인증 상태 캐시 (메모리)
authorized_guilds = {}

# 봇 관리자 ID (인증코드 생성 권한을 가진 사용자)
BOT_ADMIN_ID = 1161916637428060270

# 서버별 첫 명령어 사용자 추적
first_command_users = {}

# 데이터베이스에서 인증된 서버 목록 로드
def load_authorized_guilds():
    global authorized_guilds
    
    # MongoDB에서 인증 데이터 로드
    if db.is_mongo_connected():
        mongo_guilds = db.load_authorized_guilds()
        authorized_guilds = mongo_guilds
        print(f"MongoDB에서 인증된 서버 {len(authorized_guilds)}개 로드 완료")
    else:
        print("⚠️ MongoDB에 연결되어 있지 않습니다. 인증된 서버 데이터를 로드할 수 없습니다.")

# 초기 로딩
load_authorized_guilds()

# 서버의 인증 상태 확인
def is_guild_authorized(guild_id):
    if not db.is_mongo_connected():
        return False
    return guild_id in authorized_guilds or db.is_guild_authorized(guild_id)

# 인증 코드 생성 함수 (SQLite 대신 MongoDB 사용)
def generate_auth_code():
    if not db.is_mongo_connected():
        print("⚠️ MongoDB에 연결되어 있지 않습니다. 인증 코드를 생성할 수 없습니다.")
        return None
    return db.generate_auth_code()

# 인증 코드 유효성 검증 함수
def validate_auth_code(code):
    if not db.is_mongo_connected():
        return False, "MongoDB에 연결되어 있지 않습니다."
    return db.validate_auth_code(code)

# 인증 코드 사용 처리 함수
def use_auth_code(code, guild_id):
    if not db.is_mongo_connected():
        return False
        
    # MongoDB에 저장
    result = db.use_auth_code(code, guild_id)
    
    # 메모리 캐시 업데이트
    if result:
        authorized_guilds[guild_id] = True
    
    return result

# 명령어 체크 함수로 인증 상태 확인 (실행 전)
def check_auth():
    async def predicate(inter):
        if not inter.guild:
            return True
            
        # 봇 관리자는 항상 허용
        if inter.author.id == BOT_ADMIN_ID:
            return True

        if is_guild_authorized(inter.guild.id):
            return True
            
        # 관리자인 경우 인증 모달 표시
        if inter.author.guild_permissions.administrator:
            try:
                await inter.response.send_modal(
                    title="봇 인증",
                    custom_id="bot_auth_modal",
                    components=[
                        disnake.ui.TextInput(
                            label="인증을 위한 16자리 코드를 입력하는 것이다!",
                            placeholder="예: AbCdEfGh12345678",
                            custom_id="auth_code",
                            style=disnake.TextInputStyle.short,
                            min_length=16,
                            max_length=16
                        ),
                        disnake.ui.TextInput(
                            label="개인정보 처리방침 동의",
                            placeholder="개인정보 처리방침(https://mofucat.jp/ko/privacy-mizuki)에 동의하는 것이냐? 동의한다면 \"동의합니다\"라고 적는 것이다.",
                            custom_id="privacy_policy",
                            style=disnake.TextInputStyle.paragraph,
                            required=True
                        )
                    ]
                )
            except disnake.errors.HTTPException:
                # 이미 응답된 경우 followup 사용
                await inter.followup.send(
                    "⚠️ 이 서버는 아직 인증되지 않은 것이다! 서버 관리자에게 문의하는 것이다!",
                    ephemeral=True
                )
        else:
            # 일반 사용자는 인증 안내 메시지만 표시
            await inter.response.send_message(
                "⚠️ 이 서버는 아직 인증되지 않은 것이다! 서버 관리자에게 문의하는 것이다!",
                ephemeral=True
            )
        return False
    return commands.check(predicate)

# 모든 슬래시 명령어에 인증 필요 설정 (전역 설정)
@bot.before_slash_command_invoke
async def before_command(inter):
    if not inter.guild:
        return
    
    # 인증 상태 확인
    if not is_guild_authorized(inter.guild.id):
        # 인증이 필요한 경우 처리
        try:
            if not inter.response.is_done():
                # 관리자인 경우 인증 모달 표시
                if inter.author.guild_permissions.administrator:
                    await inter.response.send_modal(
                        title="봇 인증",
                        custom_id="bot_auth_modal",
                        components=[
                            disnake.ui.TextInput(
                                label="인증을 위한 16자리 코드를 입력하는 것이다!",
                                placeholder="예: AbCdEfGh12345678",
                                custom_id="auth_code",
                                style=disnake.TextInputStyle.short,
                                min_length=16,
                                max_length=16
                            ),
                            disnake.ui.TextInput(
                                label="개인정보 처리방침 동의",
                                placeholder="개인정보 처리방침(https://mofucat.jp/ko/privacy-mizuki)에 동의하는 것이냐? 동의한다면 \"동의합니다\"라고 적는 것이다.",
                                custom_id="privacy_policy",
                                style=disnake.TextInputStyle.paragraph,
                                required=True
                            )
                        ]
                    )
                    # 명령어 실행 취소 - 메시지 수정
                    raise commands.CommandInvokeError("서버가_인증되지_않았습니다") # 공백 제거
                else:
                    # 일반 사용자는 관리자에게 문의하도록 안내
                    await inter.response.send_message(
                        "⚠️ 이 서버는 아직 인증되지 않은 것이다! 서버 관리자에게 문의하는 것이다!",
                        ephemeral=True
                    )
                    # 명령어 실행 취소 - 메시지 수정
                    raise commands.CommandInvokeError("서버가_인증되지_않았습니다") # 공백 제거
        except disnake.errors.HTTPException:
            # 이미 응답된 경우 추가 처리하지 않음
            pass

# 인증 모달 처리
@bot.listen("on_modal_submit")
async def on_modal_submit(inter: disnake.ModalInteraction):
    if inter.custom_id == "bot_auth_modal":
        auth_code = inter.text_values["auth_code"]
        privacy_consent = inter.text_values["privacy_policy"]
        
        # 개인정보 처리방침 동의 확인
        if privacy_consent != "동의합니다":
            await inter.response.send_message(
                "❌ 개인정보 처리방침에 '동의합니다'라고 정확히 입력해야 인증이 가능한 것이다!",
                ephemeral=True
            )
            return
        
        # 코드 검증
        valid, message = validate_auth_code(auth_code)
        
        if not valid:
            await inter.response.send_message(f"❌ {message}", ephemeral=True)
            return
        
        # 인증 코드 사용 처리
        use_auth_code(auth_code, inter.guild.id)
        
        await inter.response.send_message(
            "✅ 인증이 완료된 것이다! 이제 이 서버에서 모든 봇 기능을 사용할 수 있는 것이다!\n\n"
            "📝 개인정보 처리방침은 [여기](https://mofucat.jp/ko/privacy-mizuki)에서 언제든지 확인할 수 있는 것이다!",
            ephemeral=True
        )

# !code 명령어 제거 (주석 처리)
"""
@bot.listen('on_message')
async def code_command(message):
    # !code 명령어 감지
    if message.content.lower().startswith('!code'):
        # 권한 확인 (봇 관리자만 사용 가능)
        if message.author.id != BOT_ADMIN_ID:
            await message.channel.send("❌ 이 명령어는 봇 관리자만 사용할 수 있습니다.")
            return
        
        # 원본 메시지 삭제
        try:
            await message.delete()
        except:
            pass  # 메시지 삭제 권한이 없을 경우 무시
        
        # 새 인증 코드 생성
        auth_code = generate_auth_code()
        
        # Webhook 생성해서 ephemeral 효과 내기
        try:
            webhook = await message.channel.create_webhook(name="인증코드 전송")
            try:
                await webhook.send(
                    f"🔑 새로운 인증 코드: `{auth_code}`\n이 코드는 한 번만 사용할 수 있습니다.",
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    wait=True
                )
                # 5초 후에 메시지 삭제
                await asyncio.sleep(15)
                await webhook.delete()
            except Exception as e:
                print(f"웹훅 메시지 전송 오류: {e}")
                await webhook.delete()
        except Exception as e:
            print(f"웹훅 생성 오류: {e}")
            # 웹훅 생성 실패시 일반 메시지로 전송
            temp_msg = await message.channel.send(f"🔑 {message.author.mention}님의 새 인증 코드: ||`{auth_code}`||\n(이 메시지는 30초 후 삭제됩니다)")
            await asyncio.sleep(30)
            await temp_msg.delete()
"""

# !list 명령어 - 인증된 서버 목록 및 유효한 코드 확인/삭제
@bot.listen('on_message')
async def list_command(message):
    # 중복 실행 방지 플래그 설정
    if not hasattr(list_command, 'processing_ids'):
        list_command.processing_ids = set()
    
    if message.content.lower().startswith('!list'):
        # 중복 실행 방지
        if message.id in list_command.processing_ids:
            return
        
        list_command.processing_ids.add(message.id)
        
        try:
            # 권한 확인 (봇 관리자만 사용 가능)
            if message.author.id != BOT_ADMIN_ID:
                await message.channel.send("❌ 이 명령어는 봇 관리자만 사용할 수 있는 것이다.")
                return
            
            # 원본 명령어 메시지 삭제
            try:
                await message.delete()
            except:
                pass
            
            # 설정 중 메시지
            setup_msg = await message.channel.send(f"⚙️ {message.author.mention}님의 인증 관리 패널을 설정 중인 것이다...")
            
            # AuthManageView 클래스 정의
            class AuthManageView(disnake.ui.View):
                def __init__(self, author_id, setup_message, panel_message=None):
                    super().__init__(timeout=300)  # 5분 타임아웃
                    self.author_id = author_id
                    self.page = 1
                    self.item_type = "server"  # 'server' 또는 'code'
                    self.setup_message = setup_message
                    self.panel_message = panel_message
                
                # 버튼 클릭 처리를 위한 interaction_check 오버라이드
                async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
                    # 권한 확인
                    if inter.author.id != self.author_id:
                        await inter.response.send_message("다른 사람의 명령어 결과는 조작할 수 없는 것이다.", ephemeral=True)
                        return False
                    
                    # 커스텀 ID 처리
                    custom_id = inter.component.custom_id
                    
                    # 종료 버튼 처리
                    if custom_id == "close_panel":
                        # 메시지 삭제 처리
                        await self.close_panel(inter)
                        return False
                    
                    # 서버/코드 관리 버튼
                    if custom_id == "manage_servers":
                        self.item_type = "server"
                        self.page = 1
                        await self.show_management_page(inter)
                        return False
                        
                    elif custom_id == "manage_codes":
                        self.item_type = "code"
                        self.page = 1
                        await self.show_management_page(inter)
                        return False
                    
                    # 페이지 버튼
                    elif custom_id == "prev_page":
                        self.page -= 1
                        await self.show_management_page(inter)
                        return False
                    
                    elif custom_id == "next_page":
                        self.page += 1
                        await self.show_management_page(inter)
                        return False
                    
                    # 메인 메뉴 버튼
                    elif custom_id == "main_menu":
                        await inter.response.edit_message(embed=embed, view=self)
                        return False
                    
                    # 새 코드 생성 버튼
                    elif custom_id == "new_code":
                        auth_code = generate_auth_code()
                        await inter.response.send_message(f"🔑 새로운 인증 코드가 생성된 것이다: `{auth_code}`", ephemeral=True)
                        await self.show_management_page(inter)
                        return False
                    
                    # 서버 삭제 처리
                    elif custom_id.startswith("delete_server_"):
                        guild_id = int(custom_id.split("_")[2])
                        
                        # 확인 메시지
                        confirm_view = disnake.ui.View()
                        confirm_view.add_item(disnake.ui.Button(label="확인", style=disnake.ButtonStyle.danger, custom_id="confirm"))
                        confirm_view.add_item(disnake.ui.Button(label="취소", style=disnake.ButtonStyle.secondary, custom_id="cancel"))
                        
                        await inter.response.send_message(
                            f"⚠️ 정말로 서버 ID: {guild_id}의 인증을 취소할 것이냐?",
                            view=confirm_view,
                            ephemeral=True
                        )
                        
                        # 확인 응답 대기
                        try:
                            confirm_inter = await bot.wait_for(
                                "button_click",
                                check=lambda i: i.author.id == self.author_id and i.component.custom_id in ["confirm", "cancel"],
                                timeout=60.0
                            )
                            
                            if confirm_inter.component.custom_id == "confirm":
                                # MongoDB에서 서버 삭제
                                if db.is_mongo_connected():
                                    db.authorized_guilds_collection.delete_one({"guild_id": guild_id})
                                    
                                    # 메모리 캐시에서도 삭제
                                    if guild_id in authorized_guilds:
                                        del authorized_guilds[guild_id]
                                        
                                    await confirm_inter.response.edit_message(content="✅ 서버 인증이 취소된 것이다.", view=None)
                                    await self.show_management_page(inter)
                                else:
                                    await confirm_inter.response.edit_message(content="❌ MongoDB 연결 오류", view=None)
                            else:
                                await confirm_inter.response.edit_message(content="❌ 서버 인증 취소가 취소된 것이다.", view=None)
                        except asyncio.TimeoutError:
                            await inter.edit_original_message(content="시간이 초과된 것이다.", view=None)
                        return False
                    
                    # 코드 삭제 처리
                    elif custom_id.startswith("delete_code_"):
                        code = custom_id[len("delete_code_"):]
                        
                        # 확인 메시지
                        confirm_view = disnake.ui.View()
                        confirm_view.add_item(disnake.ui.Button(label="확인", style=disnake.ButtonStyle.danger, custom_id="confirm"))
                        confirm_view.add_item(disnake.ui.Button(label="취소", style=disnake.ButtonStyle.secondary, custom_id="cancel"))
                        
                        await inter.response.send_message(
                            f"⚠️ 정말로 코드 `{code}`를 삭제하는 것이냐?",
                            view=confirm_view,
                            ephemeral=True
                        )
                        
                        # 확인 응답 대기
                        try:
                            confirm_inter = await bot.wait_for(
                                "button_click",
                                check=lambda i: i.author.id == self.author_id and i.component.custom_id in ["confirm", "cancel"],
                                timeout=60.0
                            )
                            
                            if confirm_inter.component.custom_id == "confirm":
                                # MongoDB에서 코드 삭제
                                if db.is_mongo_connected():
                                    db.auth_codes_collection.delete_one({"code": code})
                                    await confirm_inter.response.edit_message(content="✅ 인증 코드가 삭제된 것이다.", view=None)
                                    await self.show_management_page(inter)
                                else:
                                    await confirm_inter.response.edit_message(content="❌ MongoDB 연결 오류", view=None)
                            else:
                                await confirm_inter.response.edit_message(content="❌ 코드 삭제가 취소된 것이다.", view=None)
                        except asyncio.TimeoutError:
                            await inter.edit_original_message(content="시간이 초과된 것이다.", view=None)
                        return False
                    
                    return True  # 다른 버튼은 원래 핸들러로 처리
                    
                async def show_management_page(self, inter):
                    if self.item_type == "server":
                        await self.show_servers_page(inter)
                    else:
                        await self.show_codes_page(inter)
                
                async def show_servers_page(self, inter):
                    # MongoDB에서 서버 목록 조회 (수정된 부분)
                    if db.is_mongo_connected():
                        all_servers = []
                        # MongoDB에서 인증된 서버 목록 조회 (정렬된 리스트)
                        cursor = db.authorized_guilds_collection.find().sort("authorized_at", -1)
                        for doc in cursor:  # sync for 사용
                            all_servers.append((doc["guild_id"], doc.get("authorized_at", ""), doc.get("auth_code", "")))
                    else:
                        all_servers = []
                    
                    # 페이지네이션 처리
                    items_per_page = 5
                    total_pages = max(1, (len(all_servers) + items_per_page - 1) // items_per_page)
                    self.page = max(1, min(self.page, total_pages))
                    
                    start_idx = (self.page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    page_servers = all_servers[start_idx:end_idx]
                    
                    # 임베드 생성
                    embed = disnake.Embed(
                        title="🖥️ 인증 서버 관리",
                        description=f"페이지 {self.page}/{total_pages}",
                        color=disnake.Color.blue()
                    )
                    
                    for i, (guild_id, auth_date, auth_code) in enumerate(page_servers, start_idx + 1):
                        guild = bot.get_guild(guild_id)
                        name = guild.name if guild else f"알 수 없는 서버 (ID: {guild_id})"
                        
                        # 인증 날짜 포맷팅
                        date_str = auth_date.strftime("%Y-%m-%d %H:%M") if isinstance(auth_date, datetime.datetime) else "날짜 정보 없음"
                            
                        embed.add_field(
                            name=f"{i}. {name}",
                            value=f"ID: `{guild_id}`\n인증일: {date_str}\n인증코드: `{auth_code[:8]}...`" if auth_code else f"ID: `{guild_id}`\n인증일: {date_str}",
                            inline=False
                        )
                    
                    # 페이지 버튼 초기화
                    self.clear_items()
                    
                    # 페이지네이션 버튼
                    if total_pages > 1:
                        if self.page > 1:
                            self.add_item(disnake.ui.Button(label="이전", style=disnake.ButtonStyle.secondary, custom_id="prev_page"))
                        if self.page < total_pages:
                            self.add_item(disnake.ui.Button(label="다음", style=disnake.ButtonStyle.secondary, custom_id="next_page"))
                    
                    # 메인 메뉴 버튼
                    self.add_item(disnake.ui.Button(label="메인 메뉴", style=disnake.ButtonStyle.primary, custom_id="main_menu"))
                    
                    # 삭제 버튼
                    if page_servers:
                        for i, (guild_id, _, _) in enumerate(page_servers):
                            self.add_item(disnake.ui.Button(
                                label=f"{start_idx + i + 1}번 삭제", 
                                style=disnake.ButtonStyle.danger, 
                                custom_id=f"delete_server_{guild_id}"
                            ))
                    
                    if inter.response.is_done():
                        await inter.edit_original_message(embed=embed, view=self)
                    else:
                        await inter.response.edit_message(embed=embed, view=self)
                
                async def show_codes_page(self, inter):
                    # MongoDB에서 미사용 인증 코드 조회 (수정된 부분)
                    if db.is_mongo_connected():
                        all_codes = []
                        cursor = db.auth_codes_collection.find({"used": False}).sort("created_at", -1)
                        for doc in cursor:  # sync for 사용
                            all_codes.append((doc["code"], doc.get("created_at", "")))
                    else:
                        all_codes = []
                    
                    # 페이지네이션 처리
                    items_per_page = 5
                    total_pages = max(1, (len(all_codes) + items_per_page - 1) // items_per_page)
                    self.page = max(1, min(self.page, total_pages))
                    
                    start_idx = (self.page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    page_codes = all_codes[start_idx:end_idx]
                    
                    # 임베드 생성
                    embed = disnake.Embed(
                        title="🔑 인증 코드 관리",
                        description=f"페이지 {self.page}/{total_pages}",
                        color=disnake.Color.green()
                    )
                    
                    for i, (code, created_at) in enumerate(page_codes, start_idx + 1):
                        # 날짜 포맷팅
                        date_str = created_at.strftime("%Y-%m-%d %H:%M") if isinstance(created_at, datetime.datetime) else "날짜 정보 없음"
                            
                        embed.add_field(
                            name=f"{i}. 인증코드",
                            value=f"코드: `{code}`\n생성일: {date_str}",
                            inline=False
                        )
                    
                    # 페이지 버튼 초기화
                    self.clear_items()
                    
                    # 새 코드 생성 버튼
                    self.add_item(disnake.ui.Button(label="새 코드 생성", style=disnake.ButtonStyle.success, custom_id="new_code"))
                    
                    # 페이지네이션 버튼
                    if total_pages > 1:
                        if self.page > 1:
                            self.add_item(disnake.ui.Button(label="이전", style=disnake.ButtonStyle.secondary, custom_id="prev_page"))
                        if self.page < total_pages:
                            self.add_item(disnake.ui.Button(label="다음", style=disnake.ButtonStyle.secondary, custom_id="next_page"))
                    
                    # 메인 메뉴 버튼
                    self.add_item(disnake.ui.Button(label="메인 메뉴", style=disnake.ButtonStyle.primary, custom_id="main_menu"))
                    
                    # 삭제 버튼
                    if page_codes:
                        for i, (code, _) in enumerate(page_codes):
                            self.add_item(disnake.ui.Button(
                                label=f"{start_idx + i + 1}번 삭제", 
                                style=disnake.ButtonStyle.danger, 
                                custom_id=f"delete_code_{code}"
                            ))
                    
                    if inter.response.is_done():
                        await inter.edit_original_message(embed=embed, view=self)
                    else:
                        await inter.response.edit_message(embed=embed, view=self)
                
                # 종료 버튼 핸들러
                @disnake.ui.button(label="종료", style=disnake.ButtonStyle.danger, custom_id="close_panel")
                async def close_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                    await self.close_panel(inter)
                
                # 패널 종료 함수
                async def close_panel(self, inter):
                    try:
                        # 먼저 인터랙션에 응답
                        await inter.response.send_message("인증 패널을 종료하는 것이다.", ephemeral=True)
                        
                        # 설정 메시지 삭제
                        await self.setup_message.delete()
                        
                        # 패널 메시지 삭제
                        if self.panel_message:
                            await self.panel_message.delete()
                    except Exception as e:
                        print(f"패널 종료 중 오류: {e}")
            
            # MongoDB에서 서버 및 코드 정보 조회 (수정된 부분)
            server_rows = []
            code_rows = []
            
            if db.is_mongo_connected():
                # 인증된 서버 조회
                server_cursor = db.authorized_guilds_collection.find().sort("authorized_at", -1)
                for doc in server_cursor:
                    server_rows.append((doc["guild_id"], doc.get("authorized_at", ""), doc.get("auth_code", "")))
                
                # 사용되지 않은 인증 코드 조회
                code_cursor = db.auth_codes_collection.find({"used": False}).sort("created_at", -1)
                for doc in code_cursor:
                    code_rows.append((doc["code"], doc.get("created_at", "")))
            
            # 종합 임베드 생성
            embed = disnake.Embed(
                title="🔐 인증 관리 패널",
                description=f"**{message.author.mention}님만 조작할 수 있는 패널인 것이다**\n다른 사용자는 버튼을 사용할 수 없는 것이다.\n\n"
                          f"📝 [개인정보 처리방침](https://mofucat.jp/ko/privacy-mizuki)",
                color=disnake.Color.blue()
            )
            
            # 서버 목록 추가
            servers_value = ""
            for i, (guild_id, auth_date, auth_code) in enumerate(server_rows, 1):
                try:
                    guild = bot.get_guild(guild_id)
                    display_name = guild.name if guild else f"알 수 없는 서버 (ID: {guild_id})"
                    
                    # 인증 날짜 포맷팅
                    try:
                        auth_date = datetime.datetime.strptime(auth_date[:19], "%Y-%m-%d %H:%M:%S")
                        date_str = auth_date.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_str = "날짜 정보 없음"
                    
                    servers_value += f"{i}. **{display_name}**\n"
                    servers_value += f"   ID: `{guild_id}` | 인증일: {date_str}\n"
                except Exception as e:
                    print(f"서버 정보 처리 오류: {e}")
                    servers_value += f"{i}. **ID: {guild_id}** (오류 발생)\n"
                    
                # 10개 이상이면 생략
                if i >= 10 and len(server_rows) > 10:
                    servers_value += f"_외 {len(server_rows) - 10}개 서버..._\n"
                    break
                    
            embed.add_field(
                name=f"🖥️ 인증된 서버 ({len(server_rows)}개)",
                value=servers_value if servers_value else "인증된 서버가 없습니다.",
                inline=False
            )
            
            # 유효한 코드 목록 추가
            codes_value = ""
            for i, (code, created_at) in enumerate(code_rows, 1):
                # 날짜 포맷팅
                try:
                    c_date = datetime.datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
                    date_str = c_date.strftime("%Y-%m-%d %H:%M")
                except:
                    date_str = "날짜 정보 없음"
                    
                codes_value += f"{i}. `{code}` (생성일: {date_str})\n"
                
                # 10개 이상이면 생략
                if i >= 10 and len(code_rows) > 10:
                    codes_value += f"_외 {len(code_rows) - 10}개 코드..._\n"
                    break
                    
            embed.add_field(
                name=f"🔑 유효한 인증 코드 ({len(code_rows)}개)",
                value=codes_value if codes_value else "유효한 인증 코드가 없는 것이다!.",
                inline=False
            )
            
            embed.set_footer(text=f"이 패널은 {message.author.display_name}님만 사용할 수 있는 것이다!.")
            
            # 초기 뷰 생성 (합친 패널)
            initial_view = AuthManageView(message.author.id, setup_msg)
            initial_view.add_item(disnake.ui.Button(label="서버 관리", style=disnake.ButtonStyle.primary, custom_id="manage_servers"))
            initial_view.add_item(disnake.ui.Button(label="코드 관리", style=disnake.ButtonStyle.primary, custom_id="manage_codes"))
            initial_view.add_item(disnake.ui.Button(label="새 코드 생성", style=disnake.ButtonStyle.success, custom_id="new_code"))
            
            # 설정 메시지에 답장으로 패널 메시지 전송
            panel_msg = await setup_msg.reply(
                content=f"🔒 **{message.author.mention}님의 인증 관리 패널** (다른 사용자는 버튼을 사용할 수 없는 것이다)",
                embed=embed,
                view=initial_view
            )
            
            # 패널 메시지 참조 저장
            initial_view.panel_message = panel_msg
            
        except Exception as e:
            print(f"인증 패널 생성 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            try:
                await message.channel.send(f"❌ 오류가 발생했습니다: {e}")
            except:
                pass
        finally:
            list_command.processing_ids.discard(message.id)

