def normalize(p: str) -> str:
    """ Transform p to Unix-style by replacing backslashes """
    return p.replace('\\', '/')
