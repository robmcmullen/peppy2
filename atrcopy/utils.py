import types

import numpy as np

import logging
log = logging.getLogger(__name__)


def to_numpy(value):
    if type(value) is np.ndarray:
        return value
    elif type(value) is types.StringType:
        return np.fromstring(value, dtype=np.uint8)
    elif type(value) is types.ListType:
    	return np.asarray(value, dtype=np.uint8)
    raise TypeError("Can't convert to numpy data")


def to_numpy_list(value):
    if type(value) is np.ndarray:
        return value
    return np.asarray(value, dtype=np.uint32)


class WriteableSector(object):
    def __init__(self, sector_size, data=None, num=-1):
        self._sector_num = num
        self._next_sector = 0
        self.sector_size = sector_size
        self.file_num = 0
        self.data = np.zeros([sector_size], dtype=np.uint8)
        self.used = 0
        self.ptr = self.used
        if data is not None:
            self.add_data(data)

    def __str__(self):
        return "sector=%d next=%d size=%d used=%d" % (self._sector_num, self._next_sector, self.sector_size, self.used)

    @property
    def sector_num(self):
        return self._sector_num

    @sector_num.setter
    def sector_num(self, value):
        self._sector_num = value

    @property
    def next_sector_num(self):
        return self._next_sector_num

    @sector_num.setter
    def next_sector_num(self, value):
        self._next_sector_num = value

    @property
    def space_remaining(self):
        return self.sector_size - self.ptr

    @property
    def is_empty(self):
        return self.ptr == 0

    def add_data(self, data):
        count = len(data)
        if self.ptr + count > self.sector_size:
            count = self.space_remaining
        self.data[self.ptr:self.ptr + count] = data[0:count]
        self.ptr += count
        self.used += count
        return data[count:]


class BaseSectorList(object):
    def __init__(self, sector_size):
        self.sector_size = sector_size
        self.sectors = []

    def __len__(self):
        return len(self.sectors)

    def __getitem__(self, index):
        if index < 0 or index >= len(self):
            raise IndexError
        return self.sectors[index]

    @property
    def num_sectors(self):
        return len(self.sectors)

    @property
    def first_sector(self):
        if self.sectors:
            return self.sectors[0].sector_num
        return -1

    def append(self, sector):
        self.sectors.append(sector)


class Directory(BaseSectorList):
    def __init__(self, header, num_dirents=-1, sector_class=WriteableSector):
        BaseSectorList.__init__(self, header.sector_size)
        self.sector_class = sector_class
        self.num_dirents = num_dirents
        # number of dirents may be unlimited, so use a dict instead of a list
        self.dirents = {}

    def set(self, index, dirent):
        self.dirents[index] = dirent
        log.debug("set dirent #%d: %s" % (index, dirent))

    def get_free_dirent(self):
        used = set()
        d = self.dirents.items()
        d.sort()
        for i, dirent in d:
            if not dirent.in_use:
                return i
            used.add(i)
        if self.num_dirents > 0 and (len(used) >= self.num_dirents):
            raise NoSpaceInDirectory()
        i += 1
        used.add(i)
        return i

    def add_dirent(self, filename, filetype):
        index = self.get_free_dirent()
        dirent = self.dirent_class(None)
        dirent.set_values(filename, filetype, index)
        self.set(index, dirent)
        return dirent

    def find_dirent(self, filename):
        for dirent in self.dirents.values():
            if filename == dirent.get_filename():
                return dirent
        raise FileNotFound("%s not found on disk" % filename)

    def save_dirent(self, image, dirent, vtoc, sector_list):
        self.place_sector_list(dirent, vtoc, sector_list)
        dirent.update_sector_info(sector_list)
        self.calc_sectors(image)

    def place_sector_list(self, dirent, vtoc, sector_list):
        """ Map out the sectors and link the sectors together

        raises NotEnoughSpaceOnDisk if the whole file won't fit. It will not
        allow partial writes.
        """
        sector_list.calc_extra_sectors()
        num = len(sector_list)
        order = vtoc.reserve_space(num)
        if len(order) != num:
            raise InvalidFile("VTOC reserved space for %d sectors. Sectors needed: %d" % (len(order), num))
        file_length = 0
        last_sector = None
        for sector, sector_num in zip(sector_list.sectors, order):
            sector.sector_num = sector_num
            sector.file_num = dirent.file_num
            file_length += sector.used
            if last_sector is not None:
                last_sector.next_sector_num = sector_num
            last_sector = sector
        if last_sector is not None:
            last_sector.next_sector_num = 0
        sector_list.file_length = file_length

    def remove_dirent(self, image, dirent, vtoc, sector_list):
        vtoc.free_sector_list(sector_list)
        dirent.mark_deleted()
        self.calc_sectors(image)

    @property
    def dirent_class(self):
        raise NotImplementedError

    def calc_sectors(self, image):
        self.sectors = []
        self.current_sector = self.get_dirent_sector()
        self.encode_index = 0

        d = self.dirents.items()
        d.sort()
        # there may be gaps, so fill in missing entries with blanks
        current = 0
        for index, dirent in d:
            for missing in range(current, index):
                log.debug("Encoding empty dirent at %d" % missing)
                data = self.encode_empty()
                self.store_encoded(data)
            log.debug("Encoding dirent: %s" % dirent)
            data = self.encode_dirent(dirent)
            self.store_encoded(data)
            current = index + 1
        self.finish_encoding(image)

    def get_dirent_sector(self):
        return self.sector_class(self.sector_size)

    def encode_empty(self):
        raise NotImplementedError

    def encode_dirent(self, dirent):
        raise NotImplementedError

    def store_encoded(self, data):
        while True:
            log.debug("store_encoded: %d bytes in %s" % (len(data), self.current_sector))
            data = self.current_sector.add_data(data)
            if len(data) > 0:
                self.sectors.append(self.current_sector)
                self.current_sector = self.get_dirent_sector()
            else:
                break

    def finish_encoding(self, image):
        if not self.current_sector.is_empty:
            self.sectors.append(self.current_sector)
        self.set_sector_numbers(image)

    def set_sector_numbers(self, image):
        raise NotImplementedError


class VTOC(BaseSectorList):
    def __init__(self, header, segments=None):
        BaseSectorList.__init__(self, header.sector_size)

        # sector map: 1 is free, 0 is allocated
        self.sector_map = np.zeros([1280], dtype=np.uint8)
        if segments is not None:
            self.parse_segments(segments)

    def parse_segments(self, segments):
        raise NotImplementedError

    def reserve_space(self, num):
        order = []
        for i in range(num):
            order.append(self.get_next_free_sector())
        log.debug("Sectors reserved: %s" % order)
        self.calc_bitmap()
        return order

    def get_next_free_sector(self):
        free = np.nonzero(self.sector_map)[0]
        if len(free) > 0:
            num = free[0]
            log.debug("Found sector %d free" % num)
            self.sector_map[num] = 0
            return num
        raise NotEnoughSpaceOnDisk("No space left in VTOC")

    def calc_bitmap(self):
        raise NotImplementedError

    def free_sector_list(self, sector_list):
        for sector in sector_list:
            self.sector_map[sector.sector_num] = 1


class SectorBuilder(BaseSectorList):
    def __init__(self, header, usable, data, sector_class):
        BaseSectorList.__init__(self, header.sector_size)
        self.data = to_numpy(data)
        self.usable_bytes = usable
        self.split_into_sectors(header)
        self.file_length = -1

    def split_into_sectors(self, header):
        index = 0
        while index < len(self.data):
            count = min(self.usable_bytes, len(self.data) - index)
            sector = header.create_sector(self.data[index:index + count])
            self.sectors.append(sector)
            index += count


    def calc_extra_sectors(self):
        """ Add extra sectors to the list.

        For example, DOS 3.3 uses a track/sector list at the beginning
        of the file

        Sectors will have their sector assignments when this function is
        called.
        """
        pass
