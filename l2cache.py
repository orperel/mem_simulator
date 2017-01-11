from mem_ifc import MemoryInterface


class L2Cache(MemoryInterface):

    # L2 Cache parameters defined here
    CACHE_SIZE_IN_BYTES = 32 * 1024  # Mem capacity is 32K for each set
    MEM_BUS_WIDTH = 256  # In bits
    MEM_HIT_TIME = 4  # In clock cycles

    # L2 Cache contents, initialized to 0 until data is accessed
    mem0 = [0] * CACHE_SIZE_IN_BYTES
    mem1 = [0] * CACHE_SIZE_IN_BYTES

    def __init__(self, next_mem_arg: MemoryInterface, block_size: int):
        """
        C'tor for L2 Cache object, initialized to 0 for each mem cell in the beginning of each simulation.
        :param next_mem_arg: A pointer to the next memory level in the hierarchy (L2 cache or Main memory)
        :param block_size: Block size for this level of cache (atomic actions operate on this amount of bytes).
        """
        super(L2Cache, self).__init__(next_mem_arg)  # Call super constructor with next level of hierarchy
        self.block_size = block_size

    def is_address_present(self, address: int) -> bool:
        """
        Query if the data in the given address is present in the current memory level
        :param address: Address to query if the data is contained in the current memory level
        :return: True if the memory of this address resides in the current mem level, false is not.
        """
        return False  # TODO: Implement

    def read_miss_callback(self, address: int, block_size: int, data=[]) -> int:
        """
        This callback is triggered when a cache read miss occurred in the current mem level and the data now
        arrived from the next mem level.
        We write the data to the current cache level, according to write-allocate policy.
        Since block sizes may be different across cache levels, we assume that bigger blocks that arrive from the
        next level are simply truncated to the current block size.
        :param address: The address of the data requested
        :param block_size: The block size of the data requested
        :param data: The data retrieved from the next mem level
        :return: (clock cycles elapsed as int)
        """
        pass    # TODO: Implement

    def write_miss_callback(self, address: int, block_size: int) -> int:
        """
        This callback is triggered when a write cache miss occurred in the current mem level and
        dirty data should now be handled before write process can resume.
        :param address: Address of block to flush, 4 byte aligned
        :param block_size: Block size to flush to next memory, in amount of bytes
        :return: (clock cycles elapsed as int)
        """
        pass

    def write(self, address: int, block_size: int, data=[]) -> int:
        """
        Save the data to the given address.
        :param address: Address to write to, 4 byte aligned
        :param block_size: Block size to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int)
        """
        return 0  # TODO: Implement

    def read(self, address: int, block_size: int) -> (list, int):
        """
        Perform read operation from the memory, using the memory's inner logic.
        This method assumes the data is stored in the cache, and is valid.
        :param address: Address to read from, 4 byte aligned
        :param block_size: Block size to read from memory and return to previous level, in amount of bytes.
                           This is not necessarily the L2Cache block_size, the previous level may request less bytes
                           to transfer on the bus (therefore L2Cache may return a smaller block than it loads).
        :return: (data read as list of bytes, clock cycles elapsed as int)
        """
        return None  # TODO: Implement

    def dump_output_file(self, *file_names):
        """ Dumps the contents of memory hierarchy to the file names given as argument.
            Each level may use one or two files, and pass the rest of the list to the next level.
            For example: (l1.txt, l2way0.txt, l2way1.txt, memout.txt), L1 will use l1.txt and pass
            (l2way0.txt, l2way1.txt, memout.txt) to L2 cache, which passes (memout.txt) to MainMemory.
            The format used in each file is byte-per-line, no headers or footers."""
        way0_file_name = file_names[0]
        way1_file_name = file_names[1]
        self.dump_output_file(way0_file_name, self.mem0)
        self.dump_output_file(way1_file_name, self.mem1)
        self.next_mem.dump_output_file(file_names[2:])

    def print_mem(self, limit=-1):
        self.next_mem.print_mem(limit)
        # TODO: Implement..?
        return
