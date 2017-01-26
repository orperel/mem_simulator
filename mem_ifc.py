import abc
from sim_constants import CPU_DATA_SIZE


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
    def get_block_size(self) -> int:
        """
        :return: The block size in bytes for the current memory level.
        """
        pass

    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
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
        pass

    @abc.abstractmethod
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
                  writen data on the bus from the PREVIOUS memory level to the current memory level)
        """
        pass

    def load(self, address: int, block_size: int) -> (list, int):
        """
        Loads data from the given address, and updates statistics. Delegates to next mem level if needed.
        :param address: Address to read from, 4 byte aligned
        :param block_size: Block size the previous memory level requested to read from memory, in amount of bytes
        :return: (data read as list of bytes, clock cycles elapsed as int)
        """
        if self.is_address_present(address):  # Cache hit (or memory hit)
            self.read_hits += 1
            return self.read(address, block_size)
        else:  # Cache miss
            self.read_misses += 1

            # Fetch entire block from next level
            block_start_address = address - (address % self.get_block_size())
            fetched_block, cycles_elapsed = self.next_mem.load(block_start_address, self.get_block_size())

            # Data now arrived from next level..
            # Before we write it to the current mem level, flush old dirty blocks if needed
            # The memory level should decide if data should be written to next level or not, according to status bits.
            flush_cycles = self.flush_if_needed(address)
            cycles_elapsed += flush_cycles

            # Update the cache with the missing data, according to write-allocate policy
            # We don't count the clock cycles elapsed here since no data is transferred on the bus (this was accounted
            # for during the load above)
            mark_dirty = False
            self.write(block_start_address, mark_dirty, self.get_block_size(), fetched_block)

            # Perform a read to calculate read hit time that should be added for data transfer on the bus
            # Fetched block here should be identical to the
            read_cycles = self.read(address, block_size)[1]
            cycles_elapsed += read_cycles

            return fetched_block, cycles_elapsed

    def store(self, address: int, block_size: int, data=[]) -> int:
        """
        Save the data to the given address, and updates statistics. Delegates to next mem level if needed.
        :param address: Address to write to, 4 byte aligned
        :param block_size: Block size the previous memory level requested to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int)
        """
        if self.is_address_present(address):
            self.write_hits += 1
            mark_dirty = True
            return self.write(address, mark_dirty, block_size, data)
        else:
            self.write_misses += 1

            # Fetch entire block from next level
            block_start_address = address - (address % self.get_block_size())
            fetched_block, cycles_elapsed = self.next_mem.load(block_start_address, self.get_block_size())

            # Data now arrived from next level..
            # Before we write it to the current mem level, flush old dirty blocks if needed
            # The memory level should decide if data should be written to next level or not, according to status bits.
            flush_cycles = self.flush_if_needed(address)
            cycles_elapsed += flush_cycles

            # Update the cache with the missing fetched block, according to write-allocate policy.
            # We don't sum more clock cycles here because we've already counted them in the load call above
            mark_dirty = False
            self.write(block_start_address, mark_dirty, self.get_block_size(), fetched_block)

            # Now update the cache with the new data we've been tasked to store.
            # Here we pay the "hit time" - of transferring data on the bus between the prev and current memory levels.
            mark_dirty = True
            write_cycles = self.write(address, mark_dirty, block_size, data)
            cycles_elapsed += write_cycles

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
