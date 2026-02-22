def test_runtime_surface_imports() -> None:
    """Coverage + regression lock: runtime surface must remain importable."""

    from adamantine.v1.runtime import (  # noqa: F401
        AdamantineRuntimeAdapter,
        RuntimeClock,
        RuntimeExecutorProvider,
        RuntimeNonceStoreProvider,
        RuntimePolicyProvider,
        RuntimeServices,
    )
