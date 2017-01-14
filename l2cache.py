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

    def get_block_size(self) -> int:
        """
        :return: The block size in bytes for L2 Cache
        """
        return self.block_size

    def flush_if_needed(self, address: int) -> int:
        """
        This callback is triggered after a new block is loaded from the next mem level,
        and it may conflict with an older block currently residing in the cache (identical block numbers).
        This method checks if the old block is dirty and valid,
        and if needed it will take care to flush it to the next level, according to the cache logic.
        :param address: Address of new block we wish to write, 4 byte aligned.
                        This address's tag may conflict with an older block with similar block number and a
                        different tag, in which case we flush the old block.
        :return: (clock cycles elapsed to flush old block as int -  0 if no flush have occurred)
        """
        return 0  # TODO: Implement

    def write(self, address: int, mark_dirty: bool, data_size: int, data=[]) -> int:
        """
        Save the data to the given address.
        Data will be marked as "valid" and possibly "dirty", according to write-back policy.
        Handling dirty data that already occupies the cache is not the concern of this method,
        we assume that all data that should be committed have already been taken care of.
        This method may update only part of the block, or an entire block, according to data_size given.
        :param address: Address to write to, 4 byte aligned
        :param mark_dirty: When true, the written block will be marked as dirty. False when not.
        :param data_size: Data size to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int - this is the amount of cycles expected to take to transfer the
                  writen data on the bus from the L1 cache to the L2 cache)
        """
        return 0  # TODO: Implement

    def read(self, address: int, data_size: int) -> (list, int):
        """
        Perform read operation from the memory, using the memory's inner logic.
        This method assumes the data is stored in the cache, and is valid.
        :param address: Address to read from, 4 byte aligned
        :param data_size: Amount of data in bytes to read from current memory level and return to previous level.
                          Note this is not necessarily the block size: the previous level may request less bytes
                          to transfer on the bus.
        :return: (data read as list of bytes, clock cycles elapsed as int to pass this data to previous mem level)
        """
        return None  # TODO: Implement

    def dump_memory(self, *file_names):
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
