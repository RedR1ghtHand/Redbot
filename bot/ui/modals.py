import discord
from discord import Interaction, TextStyle, ui


class RenameModal(ui.Modal, title="Rename Your Voice Channel"):
    def __init__(self, channel, owner):
        super().__init__()
        self.channel = channel
        self.owner = owner
 
        self.name_input = ui.TextInput(
            label="New channel name",
            placeholder="Enter a name (1-100 chars)",
            max_length=100,
            style=TextStyle.short
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the channel owner can rename this VC!", ephemeral=True
            )
            return

        new_name = self.name_input.value.strip()
        if not new_name:
            await interaction.response.send_message(
                "Channel name cannot be empty.", ephemeral=True
            )
            return

        await self.channel.edit(name=new_name)
        await interaction.response.send_message(
            f"Channel renamed to **{new_name}**!", ephemeral=True
        )

class SetLimitModal(ui.Modal, title="Set Voice Channel Limit"):
    def __init__(self, channel, owner):
        super().__init__()
        self.channel = channel
        self.owner = owner

        self.limit_input = ui.TextInput(
            label="Enter limit",
            placeholder="Must be a number 1-99(0 for unlimited)",
            style=TextStyle.short,
            max_length=2,
        )
        self.add_item(self.limit_input)

    async def on_submit(self, interaction: Interaction):
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "Only the channel owner can change the limit!", ephemeral=True
            )
            return

        try:
            new_limit = int(self.limit_input.value)
            if new_limit < 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Invalid number. Must be 0 or positive integer.", ephemeral=True
            )
            return

        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            f"Channel limit set to {new_limit}.", ephemeral=True
        )
        