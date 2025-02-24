import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput

intents = discord.Intents.default()
intents.voice_states = True  # Para monitorar eventos de voz
intents.guilds = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variáveis para armazenar canais e mensagens
voice_channel_id = 1343304625142366330  # Canal de voz específico
text_channel_id = 1343284352053674067  # Canal de texto específico
global_message = None
temp_channels = {}  # Para armazenar os canais temporários e quem os criou


class CreateChannelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Criar Sala", style=discord.ButtonStyle.green, custom_id="create_room")
    async def create_room(self, interaction: discord.Interaction, button: Button):
        # Remover a interface antiga para evitar conflito
        self.stop()

        # Iniciar o processo de nomear a sala
        modal = Modal(title="Nome da Sala")
        name_input = TextInput(label="Digite o nome da sala:", placeholder="Ex: Squad 1", required=True)
        modal.add_item(name_input)

        # Ao enviar o modal, ele será chamado aqui
        async def modal_submit(interaction: discord.Interaction):
            room_name = name_input.value
            guild = interaction.guild
            member = interaction.user

            temp_channel_category = discord.utils.get(guild.categories, id=1269011595921592340)

            # Criação do canal temporário
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False),
                member: discord.PermissionOverwrite(connect=True, manage_channels=True)
            }
            temp_channel = await guild.create_voice_channel(room_name, category=temp_channel_category, overwrites=overwrites)

            # Mover o usuário para o canal criado
            await member.move_to(temp_channel)

            # Armazenar a sala e quem a criou
            temp_channels[temp_channel.id] = member.id

            # Adicionar botões de ação para a sala
            view = ManageChannelView(temp_channel)
            await interaction.response.send_message(f"Sala {room_name} criada e você foi movido para lá!", view=view, ephemeral=True)

        modal.on_submit = modal_submit  # Conectar a função ao submit do modal
        await interaction.response.send_modal(modal)


class ManageChannelView(View):
    def __init__(self, temp_channel):
        super().__init__(timeout=None)
        self.temp_channel = temp_channel

    @discord.ui.button(label="Excluir Sala", style=discord.ButtonStyle.red, custom_id="delete_room")
    async def delete_room(self, interaction: discord.Interaction, button: Button):
        if temp_channels.get(self.temp_channel.id) == interaction.user.id:
            await self.temp_channel.delete()
            del temp_channels[self.temp_channel.id]
            await interaction.response.send_message("Sala excluída!", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para excluir esta sala.", ephemeral=True)

    @discord.ui.button(label="Trancar Sala", style=discord.ButtonStyle.grey, custom_id="lock_room")
    async def lock_room(self, interaction: discord.Interaction, button: Button):
        if temp_channels.get(self.temp_channel.id) == interaction.user.id:
            await self.temp_channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("Sala trancada!", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para trancar esta sala.", ephemeral=True)

    @discord.ui.button(label="Abrir Sala", style=discord.ButtonStyle.blurple, custom_id="unlock_room")
    async def unlock_room(self, interaction: discord.Interaction, button: Button):
        if temp_channels.get(self.temp_channel.id) == interaction.user.id:
            await self.temp_channel.set_permissions(interaction.guild.default_role, connect=True)
            await interaction.response.send_message("Sala aberta!", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para abrir esta sala.", ephemeral=True)

    @discord.ui.button(label="Silenciar Sala", style=discord.ButtonStyle.danger, custom_id="mute_room")
    async def mute_room(self, interaction: discord.Interaction, button: Button):
        if temp_channels.get(self.temp_channel.id) == interaction.user.id:
            # Silenciar todos os membros da sala
            for member in self.temp_channel.members:
                await member.edit(mute=True)
            await interaction.response.send_message("Todos os membros foram silenciados na sala.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem permissão para silenciar esta sala.", ephemeral=True)


@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    # Monitorando o canal de texto para enviar a mensagem
    text_channel = bot.get_channel(text_channel_id)
    if text_channel:
        # Mensagem informando o monitoramento do canal de voz
        await text_channel.send("Estou monitorando o canal de voz. Quando você entrar nele, será apresentado o questionário para criar a sala.")


@bot.event
async def on_voice_state_update(member, before, after):
    # Verifica se o membro entrou no canal de voz específico
    if after.channel and after.channel.id == voice_channel_id:
        # Enviar a mensagem para o canal de texto com interação visível apenas para o usuário
        text_channel = bot.get_channel(text_channel_id)
        view = CreateChannelView()

        # Enviar a mensagem com o botão, mas como uma interação visualizada apenas para o usuário que entrou
        await text_channel.send(
            "Você entrou no canal de voz! Clique no botão abaixo para criar uma sala:", 
            view=view
        )

    # Verifica se o membro saiu da sala e se a sala está vazia
    if before.channel and before.channel.id in temp_channels:
        if len(before.channel.members) == 0:
            await before.channel.delete()
            del temp_channels[before.channel.id]


bot.run("MTMzMjc2MDEyMjI0MTMyMzAzOA.GTjD0v.abvjhyKqBtOiwKVXLwsGOpNhOXec9XiSL8MCX8")
