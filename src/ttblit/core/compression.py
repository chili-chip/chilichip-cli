from math import ceil

from construct import Adapter


class BitWriter:
    """Packs values MSB first. The last byte is padded with zero bits."""
    def __init__(self):
        self.value = 0
        self.length = 0

    def write(self, value, length):
        self.value = (self.value << length) | value
        self.length += length

    def tobytes(self):
        pad = -self.length % 8
        return (self.value << pad).to_bytes((self.length + pad) // 8, 'big')


class BitReader:
    def __init__(self, data):
        self.value = int.from_bytes(data, 'big')
        self.remaining = len(data) * 8

    def read(self, length):
        self.remaining -= length
        if self.remaining < 0:
            raise ValueError('Not enough data')
        return (self.value >> self.remaining) & ((1 << length) - 1)


class RL:
    @staticmethod
    def repetitions(seq):
        """Input: sequence of values, Output: sequence of (value, repeat count)."""
        i = iter(seq)
        prev = next(i)
        count = 1
        for v in i:
            if v == prev:
                count += 1
            else:
                yield prev, count
                prev = v
                count = 1
        yield prev, count

    @staticmethod
    def compress(data, bit_length):
        """Input: data bytes, bit length, Output: RLE'd bytes"""
        # TODO: This could be made more efficient by encoding the run-length
        # as count-n, ie 0 means a run of n, where n = break_even. Then we
        # can encode longer runs up to 255+n. But this needs changes in the
        # blit engine.
        break_even = ceil(8 / (bit_length + 1))
        bits = BitWriter()

        for value, count in RL.repetitions(data):
            while count > break_even:
                chunk = min(count, 0x100)
                bits.write(1, 1)
                bits.write(chunk - 1, 8)
                count -= chunk
                bits.write(value, bit_length)
            for x in range(count):
                bits.write(0, 1)
                bits.write(value, bit_length)
        return bits.tobytes()

    @staticmethod
    def decompress(data, bit_length, output_length):
        stream = BitReader(data)
        result = []
        while len(result) < output_length:
            count = stream.read(8) + 1 if stream.read(1) else 1
            result.extend([stream.read(bit_length)] * count)
        return bytes(result)


class PK:
    @staticmethod
    def compress(data, bit_length):
        bits = BitWriter()
        for x in data:
            bits.write(x, bit_length)
        return bits.tobytes()

    @staticmethod
    def decompress(data, bit_length, num_pixels):
        stream = BitReader(data)
        return bytes(stream.read(bit_length) for _ in range(num_pixels))


packers = {cls.__name__: cls for cls in (PK, RL)}


class ImageCompressor(Adapter):

    def bit_length(self, obj):
        """Compute the required bit length for image data.
        Uses the count of items in the palette to determine how
        densely we can pack the image data.
        """
        if obj.get('type', None) == "RW":
            return 8
        else:
            return max(1, (len(obj['data']['palette']) - 1).bit_length())

    def num_pixels(self, obj):
        return obj['data']['width'] * obj['data']['height']

    def _decode(self, obj, context, path):
        if obj['type'] != 'RW':
            obj['data']['pixels'] = packers[obj['type']].decompress(
                obj['data']['pixels'], self.bit_length(obj), self.num_pixels(obj)
            )
        return obj

    def _encode(self, obj, context, path):
        obj = obj.copy()   # we are going to mutate this, so make a deep copy
        obj['data'] = obj['data'].copy()
        bl = self.bit_length(obj)
        if obj.get('type', None) is None:
            all_comp = [(k, v.compress(obj['data']['pixels'], bl)) for k, v in packers.items()]
            best = min(all_comp, key=lambda x: len(x[1]))
            # Put the best type back into the object.
            obj['type'] = best[0]
            obj['data']['pixels'] = best[1]
        elif obj['type'] != 'RW':
            obj['data']['pixels'] = packers[obj['type']].compress(obj['data']['pixels'], bl)
        return obj
