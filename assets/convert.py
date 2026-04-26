from PIL import Image

src = Image.open("assets/icon.jpg").convert("RGBA")

# PNG for CustomTkinter
src.save("assets/icon.png")

# ICO with multiple sizes Windows expects
src.save("assets/icon.ico", format="ICO", sizes=[
    (16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)
])

print("Done — icon.png and icon.ico generated")

