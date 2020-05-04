from abc import ABCMeta


class RegistryMeta(ABCMeta):

    udes_registry = {}

    def __init__(cls, name, bases, dict):
        super(RegistryMeta, cls).__init__(name, bases, dict)
        policy_name = cls.name()

        if not policy_name:
            return

        if (
            policy_name in cls.udes_registry
            and cls.udes_registry[policy_name] is not cls
        ):
            raise ValueError("Name ({}) is already taken".format(policy_name))

        cls.udes_registry[policy_name] = cls

        # Check it has a valid interface
        instance = cls(object, False)
