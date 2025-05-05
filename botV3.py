import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.messages = True
intents.message_content = True
intents = discord.Intents.default()
intents.members = True  

bot = commands.Bot(command_prefix="!", intents=intents)

# Variáveis globais de configuração
voice_channel_id = None
category_id = None
text_channel_id = None
temp_channels = {}  # Mapeia owner_id -> (voice_channel_id, text_channel_id)
channel_owners = {}  # Mapeia voice_channel_id -> owner_id

# Modal para configuração da sala (nome e capacidade)
class ConfigRoomModal(Modal):
    def __init__(self, voice_channel: discord.VoiceChannel):
        super().__init__(title="Configurar Sala")
        self.voice_channel = voice_channel

    room_name = TextInput(
        label="Nome da sala",
        placeholder="Ex: Squad Alpha",
        required=True
    )
    capacity = TextInput(
        label="Capacidade máxima",
        placeholder="Digite um número entre 1 e 99",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            cap = int(self.capacity.value)
            if not (1 <= cap <= 99):
                raise ValueError("Fora do intervalo")
        except Exception:
            await interaction.response.send_message("Capacidade inválida. Tente novamente.", ephemeral=True)
            return

        await self.voice_channel.edit(name=self.room_name.value, user_limit=cap)
        await interaction.response.send_message("Sala atualizada com sucesso!", ephemeral=True)

# View para gerenciamento da sala temporária (configurar, trancar, destrancar, silenciar, desmutar, excluir)
class ManageRoomView(View):
    def __init__(self, voice_channel: discord.VoiceChannel, text_channel: discord.TextChannel, owner_id: int):
        super().__init__(timeout=None)
        self.voice_channel = voice_channel
        self.text_channel = text_channel
        self.owner_id = owner_id

    @discord.ui.button(label="Configurar Sala", style=discord.ButtonStyle.primary, custom_id="config_room")
    async def config_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            modal = ConfigRoomModal(self.voice_channel)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("Apenas o dono da sala pode configurar.", ephemeral=True)

    @discord.ui.button(label="Trancar Sala", style=discord.ButtonStyle.grey, custom_id="lock_room")
    async def lock_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            await self.voice_channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("Sala trancada!", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para trancar a sala.", ephemeral=True)

    @discord.ui.button(label="Destrancar Sala", style=discord.ButtonStyle.green, custom_id="unlock_room")
    async def unlock_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            await self.voice_channel.set_permissions(interaction.guild.default_role, connect=True)
            await interaction.response.send_message("Sala destrancada!", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para destrancar a sala.", ephemeral=True)

    @discord.ui.button(label="Silenciar Sala", style=discord.ButtonStyle.danger, custom_id="mute_room")
    async def mute_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            for member in self.voice_channel.members:
                await member.edit(mute=True)
            await interaction.response.send_message("Todos os membros foram silenciados na sala.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para silenciar a sala.", ephemeral=True)

    @discord.ui.button(label="Desmutar Sala", style=discord.ButtonStyle.blurple, custom_id="unmute_room")
    async def unmute_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            for member in self.voice_channel.members:
                await member.edit(mute=False)
            await interaction.response.send_message("Todos os membros foram desmutados na sala.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para desmutar a sala.", ephemeral=True)

    @discord.ui.button(label="Excluir Sala", style=discord.ButtonStyle.red, custom_id="delete_room")
    async def delete_room(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            await self.voice_channel.delete()
            await self.text_channel.delete()
            temp_channels.pop(self.owner_id, None)
            channel_owners.pop(self.voice_channel.id, None)
            await interaction.response.send_message("Sala excluída!", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para excluir a sala.", ephemeral=True)
    @discord.ui.button(label="Convidar Jogadores", style=discord.ButtonStyle.success, custom_id="invite_players")
    async def invite_players(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id == self.owner_id:
            view = InvitePlayersView(self.voice_channel, interaction)
            await interaction.response.send_message(
                "Selecione os jogadores para convidar:",
                view=view,
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Apenas o dono da sala pode convidar jogadores.", ephemeral=True)

#modal para convidar jogadores

class InvitePlayersView(View):
    def __init__(self, voice_channel: discord.VoiceChannel, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.voice_channel = voice_channel
        self.interaction = interaction
        self.selected_members = []
        
        # Carrega os membros imediatamente
        self.load_members()
    
    def load_members(self):
        # Limpa itens existentes
        self.clear_items()
        
        # Obtém todos os membros do servidor (não bots)
        all_members = [
            m for m in self.interaction.guild.members 
            if not m.bot and m != self.interaction.user
        ]
        
        # Verifica quem está realmente online (considerando mobile/desktop)
        online_members = [
            m for m in all_members 
            if m.status != discord.Status.offline or any(
                a.type == discord.ActivityType.playing for a in m.activities
            )
        ]
        
        # Se não encontrar online, mostra todos os membros (exceto bots)
        members_to_show = online_members if online_members else all_members
        
        # Divide em grupos de 25 (limite do Discord)
        chunks = [members_to_show[i:i + 25] for i in range(0, len(members_to_show), 25)]
        
        for i, chunk in enumerate(chunks):
            select = Select(
                placeholder=f"Jogadores disponíveis ({i+1}/{len(chunks)})",
                options=[
                    discord.SelectOption(
                        label=f"{m.display_name} ({'online' if m.status != discord.Status.offline else 'offline'})",
                        value=str(m.id),
                        emoji="🟢" if m.status != discord.Status.offline else "🔴"
                    ) for m in chunk
                ],
                max_values=len(chunk)
            )
            select.callback = self.select_members
            self.add_item(select)
        
        # Botão de confirmação
        confirm_button = Button(
            style=discord.ButtonStyle.success,
            label="Enviar Convites",
            custom_id="confirm_invites",
            disabled=not members_to_show
        )
        confirm_button.callback = self.confirm_invites
        self.add_item(confirm_button)
        
        # Botão de atualização
        refresh_button = Button(
            style=discord.ButtonStyle.secondary,
            label="Atualizar Lista",
            emoji="🔄",
            custom_id="refresh_list"
        )
        refresh_button.callback = self.refresh_list
        self.add_item(refresh_button)
    
    async def refresh_list(self, interaction: discord.Interaction):
        self.load_members()
        await interaction.response.edit_message(view=self)
    
    async def select_members(self, interaction: discord.Interaction):
        self.selected_members = [int(value) for value in interaction.data['values']]
        await interaction.response.defer()
    
    async def confirm_invites(self, interaction: discord.Interaction):
        if not self.selected_members:
            await interaction.response.send_message("Nenhum jogador selecionado!", ephemeral=True)
            return
        
        invited = 0
        failed = 0
        
        for member_id in set(self.selected_members):  # Remove duplicados
            member = interaction.guild.get_member(member_id)
            if member:
                try:
                    invite_msg = discord.Embed(
                        title=f"🎮 Convite para Sala de Voz",
                        description=f"{interaction.user.mention} te convidou para entrar na sala!\n\n"
                                   f"**Canal de Voz:** {self.voice_channel.mention}\n"
                                   f"**Servidor:** {interaction.guild.name}",
                        color=discord.Color.green()
                    )
                    await member.send(embed=invite_msg)
                    invited += 1
                except discord.Forbidden:
                    failed += 1
                except Exception as e:
                    print(f"Erro ao enviar convite: {e}")
                    failed += 1
        
        result_msg = f"✅ {invited} convite(s) enviado(s) com sucesso!"
        if failed > 0:
            result_msg += f"\n❌ {failed} convite(s) falharam (DMs bloqueadas ou erro)"
        
        await interaction.response.edit_message(
            content=result_msg,
            view=None
        )
        self.stop()

# View para configuração interativa via comando /setup
class SetupView(View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.interaction = interaction

        # Opções de categorias disponíveis
        categories = interaction.guild.categories
        category_options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in categories]
        self.category_select = Select(
            placeholder="Escolha uma categoria",
            options=category_options,
            custom_id="setup_category"
        )
        self.category_select.callback = self.select_category
        self.add_item(self.category_select)

        # Opções de canais de texto disponíveis
        text_channels = interaction.guild.text_channels
        text_options = [discord.SelectOption(label=tc.name, value=str(tc.id)) for tc in text_channels]
        self.text_select = Select(
            placeholder="Escolha um canal de texto",
            options=text_options,
            custom_id="setup_text"
        )
        self.text_select.callback = self.select_text_channel
        self.add_item(self.text_select)

        # Opções de canais de voz disponíveis
        voice_channels = interaction.guild.voice_channels
        voice_options = [discord.SelectOption(label=vc.name, value=str(vc.id)) for vc in voice_channels]
        self.voice_select = Select(
            placeholder="Escolha um canal de voz",
            options=voice_options,
            custom_id="setup_voice"
        )
        self.voice_select.callback = self.select_voice
        self.add_item(self.voice_select)

    async def select_category(self, interaction: discord.Interaction):
        global category_id
        category_id = int(self.category_select.values[0])
        await interaction.response.send_message(f"Categoria selecionada: <#{category_id}>", ephemeral=True)

    async def select_text_channel(self, interaction: discord.Interaction):
        global text_channel_id
        text_channel_id = int(self.text_select.values[0])
        await interaction.response.send_message(f"Canal de texto selecionado: <#{text_channel_id}>", ephemeral=True)

    async def select_voice(self, interaction: discord.Interaction):
        global voice_channel_id
        voice_channel_id = int(self.voice_select.values[0])
        await interaction.response.send_message(f"Canal de voz selecionado: <#{voice_channel_id}>", ephemeral=True)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")
    print(f"Bot conectado como {bot.user}")

@bot.event
async def on_voice_state_update(member, before, after):
    global voice_channel_id, category_id

    if not voice_channel_id or not category_id:
        return

    guild = member.guild
    category = discord.utils.get(guild.categories, id=category_id)

    if after.channel and after.channel.id == voice_channel_id:
        overwrites_voice = {
            guild.default_role: discord.PermissionOverwrite(connect=False),
            member: discord.PermissionOverwrite(connect=True, manage_channels=True)
        }
        temp_voice = await guild.create_voice_channel(f"Sala de {member.name}", category=category, overwrites=overwrites_voice)

        overwrites_text = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True)
        }
        temp_text = await guild.create_text_channel(f"CANAL-{member.name}", category=category, overwrites=overwrites_text)

        await member.move_to(temp_voice)

        temp_channels[member.id] = (temp_voice.id, temp_text.id)
        channel_owners[temp_voice.id] = member.id

        view = ManageRoomView(temp_voice, temp_text, member.id)
        await temp_text.send(f"Bem-vindo, {member.mention}! Sua sala foi criada.", view=view)

    if before.channel and before.channel.id in channel_owners:
        if len(before.channel.members) == 0:
            owner_id = channel_owners.pop(before.channel.id, None)
            if owner_id:
                temp_voice_id, temp_text_id = temp_channels.pop(owner_id, (None, None))
                temp_voice = guild.get_channel(temp_voice_id)
                temp_text = guild.get_channel(temp_text_id)
                if temp_voice:
                    await temp_voice.delete()
                if temp_text:
                    await temp_text.delete()

@bot.tree.command(name="setup", description="Configurar a categoria, canal de texto e canal de voz principal.")
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message("Selecione as configurações abaixo:", view=SetupView(interaction), ephemeral=True)

@bot.tree.command(name="orientacao", description="Enviar orientações no canal de texto configurado.")
async def orientacao(interaction: discord.Interaction):
    global text_channel_id

    if not text_channel_id:
        await interaction.response.send_message("Nenhum canal de texto foi configurado.", ephemeral=True)
        return

    channel = interaction.guild.get_channel(text_channel_id)
    if not channel:
        await interaction.response.send_message("Canal de texto configurado não encontrado.", ephemeral=True)
        return

    await channel.send(
        "🔊 **Como criar sua sala temporária:**\n"
        "1️⃣ Entre no canal de voz ➕│CRIAR CANAL DE VOZ.\n"
        "2️⃣ Uma sala de voz e um canal de texto temporários serão criados automaticamente para você.\n"
        "3️⃣ Gerencie sua sala através das opções disponíveis no canal de texto!"
    )
    await interaction.response.send_message("Orientações enviadas no canal configurado!", ephemeral=True)

bot.run("seu token")
