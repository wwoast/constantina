class ConstantinaError(Exception):
    pass

class CardNotFoundError(ConstantinaError):
    pass

class CardDateTooOldError(ConstantinaError):
    pass
