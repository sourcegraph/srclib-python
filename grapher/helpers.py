import jedi


class LineColToOffConverter(object):
    """
    Converts from (line, col) position to byte offset.
    """
    def __init__(self, source):
        source_lines = source.split('\n')
        self.cumulative_off = [0]
        for line in source_lines:
            self.cumulative_off.append(self.cumulative_off[-1] + len(line) + 1)

    def convert(self, linecol):
        """ Converts from (line, col) position to byte offset. Line is 1-indexed, col is 0-indexed. """
        line, col = linecol[0] - 1, linecol[1]  # convert line to 0-indexed
        if line >= len(self.cumulative_off):
            raise ValueError("requested line out of bounds {} > {}".format(line + 1, len(self.cumulative_off) - 1))
        return self.cumulative_off[line] + col
