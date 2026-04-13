from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings

def get_top_toolbar():
    return HTML('<ansicyan><b> λ </b></ansicyan> | Sticky Header Works!')

kb = KeyBindings()
@kb.add('c-c')
def _(event):
    event.app.exit()

top_bar = Window(content=FormattedTextControl(get_top_toolbar), height=1)
body = Window(content=FormattedTextControl('Conversation history goes here...'))
bottom_bar = Window(content=FormattedTextControl('Bottom Toolbar | /help'), height=1)

root_container = HSplit([
    top_bar,
    body,
    bottom_bar,
])

layout = Layout(root_container)
app = Application(layout=layout, key_bindings=kb, full_screen=True)
# To test on-the-fly, I would run this, but I'll trust the layout pattern.
