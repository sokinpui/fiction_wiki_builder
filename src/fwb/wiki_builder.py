from .entity_extractor import EntityExtractor


class WikiBuilder:
    """
    operation related to build wiki from book
    """

    def __init__(self, book_id: str):
        self.book_id: str = book_id

        self.entity_extractor = EntityExtractor(self.book_id)

    def process_book(self):
        """
        process book to build wiki
        """

        # reset progress of entity extractor
        self.entity_extractor.reset_progress()

        # extract entities from book and save to buffer

        # retrieve entities from buffer

        # add entities to graph

        # save to es db

        # save to graph db

        # clear buffer
