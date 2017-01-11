import abc


class MemoryInterface(object):
    """
    Base interface for all memory units in the hierarchy: MainMem, L1, L2 caches, etc.
    """
    __metaclass__ = abc.ABCMeta

    # Bridge to next memory component, to be used when data is not available in current mem level
    # I.e: L1 Cache can't perform read - it delegates to L2 cache / Main memory
    next_mem = None

    # Statistics
    read_hits = 0
    read_misses = 0
    write_hits = 0
    write_misses = 0

    def __init__(self, next_mem_arg):
        """
        Default constructor, point to next component or None
        :param next_mem_arg: A pointer to the next mem level (or None is there isn't any)
        """

        self.next_mem = next_mem_arg

    @abc.abstractmethod
    def is_address_present(self, address: int) -> bool:
        """
        Query if the data in the given address is present in the current memory level.
        :param address: Address to query if the data is contained in the current memory level
        :return: True if the memory of this address resides in the current mem level, false is not.
        """
        pass

    @abc.abstractmethod
    def read_miss_callback(self, address: int, block_size: int, data=[]) -> int:
        """
        This callback is triggered when a cache read miss occurred in the current mem level and the data now
        arrived from the next mem level.
        :param address: The address of the data requested
        :param block_size: The block size of the data requested
        :param data: The data retrieved from the next mem level
        :return: (clock cycles elapsed as int)
        """
        pass

    @abc.abstractmethod
    def write_miss_callback(self, address: int, block_size: int) -> int:
        """
        This callback is triggered when a write cache miss occurred in the current mem level and
        dirty data should now be handled before write process can resume.
        :param address: Address of block to flush, 4 byte aligned
        :param block_size: Block size to flush to next memory, in amount of bytes
        :return: (clock cycles elapsed as int)
        """
        pass

    @abc.abstractmethod
    def read(self, address: int, block_size: int) -> (list, int):
        """
        Perform read operation from the memory, using the memory's inner logic.
        This method assumes the data is stored in the memory, and is valid.
        :param address: Address to read from, 4 byte aligned
        :param block_size: Block size to read from memory, in amount of bytes.
                           This is the amount returned to the caller on the bus by the read operation.
                           The memory interface may use larger block sizes than that.
        :return: (data read as list of bytes, clock cycles elapsed as int)
        """
        pass

    @abc.abstractmethod
    def write(self, address: int, block_size: int, data=[]) -> int:
        """
        Save the data to the given address.
        :param address: Address to write to, 4 byte aligned
        :param block_size: Block size to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int)
        """
        pass

    def load(self, address: int, block_size: int) -> (list, int):
        """
        Loads data from the given address, and updates statistics. Delegates to next mem level if needed.
        :param address: Address to read from, 4 byte aligned
        :param block_size: Block size to read from memory, in amount of bytes
        :return: (data read as list of bytes, clock cycles elapsed as int)
        """
        if self.is_address_present(address):  # Cache hit (or memory hit)
            self.read_hits += 1
            return self.read(address, block_size)
        else:  # Cache miss
            self.read_misses += 1
            block_start_address = address - (address % block_size)  # Fetch entire block from next level
            data, cycles_elapsed = self.next_mem.load(block_start_address, block_size)
            cycles_elapsed += self.read_miss_callback(address, block_size, data)
            return data, cycles_elapsed

    def store(self, address: int, block_size: int, data=[]) -> int:
        """
        Save the data to the given address, and updates statistics. Delegates to next mem level if needed.
        :param address: Address to write to, 4 byte aligned
        :param block_size: Block size to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int)
        """
        if self.is_address_present(address):
            self.write_hits += 1
            return self.write(address, block_size, data)
        else:
            self.write_misses += 1

            # The memory level should decide if data should be written to next level or not, according to status bits
            cycles_elapsed = self.write_miss_callback(address, block_size)
            cycles_elapsed += self.write(address, block_size, data)
            return cycles_elapsed

    def dump_output_file(self, file_name, mem):
        """
        Helper method for dumping contents of memory to a single output file.
        :param file_name: The path of output file + name.
        :param mem: The mem (list format, iterable expected) to be dumped to file
        """
        cursor = 0  # Count number of elements printed, for newline control
        with open(file_name, 'w') as mem_out:
            for entry in mem:
                mem_out.write(str(hex(entry)[2:]).upper().zfill(2))  # Pad with 2 zeros, to uppercase, hex-format
                cursor += 1
                if len(mem) != cursor:  # Avoid newline at eof
                    mem_out.write("\n")

    @abc.abstractmethod
    def dump_memory(self, *file_names):
        """
        Dumps the contents of memory hierarchy to the file names given as argument.
        Each level may use one or two files, and pass the rest of the list to the next level.
        For example: (l1.txt, l2way0.txt, l2way1.txt, memout.txt), L1 will use l1.txt and pass
        (l2way0.txt, l2way1.txt, memout.txt) to L2 cache, which passes (memout.txt) to MainMemory.
        The format used in each file is byte-per-line, no headers or footers.
        :param file_names: A list of file names to be used as output for this point in the hierarchy and those
                           beyond it.
        """
        pass

    @abc.abstractmethod
    def print_mem(self, limit=-1):
        """Debug method for printing the contents of the current memory level"""
        pass
