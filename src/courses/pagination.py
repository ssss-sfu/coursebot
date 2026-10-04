# adds pages to the discord message
import discord


# class handles the buttons
class EmbedPaginator(discord.ui.View):
  """◀ ▶ buttons that flip through a list of embeds; only the user who ran the command can use them."""

  def __init__(self, pages: list[discord.Embed], owner_id: int, timeout: float = 120):
    super().__init__(timeout=timeout)
    self.pages = pages
    self.owner_id = owner_id
    self.index = 0
    self.message: discord.Message | None = None
    self._update_buttons()

  def _update_buttons(self):
    self.previous_page.disabled = self.index == 0
    self.next_page.disabled = self.index >= len(self.pages) - 1

  async def interaction_check(self, interaction: discord.Interaction) -> bool:
    if interaction.user.id != self.owner_id:
      await interaction.response.send_message("Only the person who ran this command can change pages.", ephemeral=True)
      return False
    return True

  async def show(self, interaction: discord.Interaction, index: int):
    self.index = max(0, min(index, len(self.pages) - 1))
    self._update_buttons()
    await interaction.response.edit_message(embed=self.pages[self.index], view=self)

  @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
  async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.show(interaction, self.index - 1)

  @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
  async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
    await self.show(interaction, self.index + 1)

  async def on_timeout(self):
    for item in self.children:
      item.disabled = True
    if self.message is not None:
      try:
        await self.message.edit(view=self)
      except discord.HTTPException:
        pass  # message deleted or interaction token expired; nothing to update


#
async def send_pages(interaction: discord.Interaction, pages: list[discord.Embed]):
  """Send one embed, or the first of several with paging buttons (after the interaction was deferred)."""
  if len(pages) == 1:
    await interaction.followup.send(embed=pages[0])
    return
  view = EmbedPaginator(pages, owner_id=interaction.user.id)
  view.message = await interaction.followup.send(embed=pages[0], view=view, wait=True)
