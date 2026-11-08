#!/usr/bin/env python3
"""Export the public profile for the explicitly selected tunnel provider."""
import sys
import host

def main():
    try:
        value=host.load_config()
        if value.get('funnel_enabled'):
            import funnel
            return 0 if funnel.show_profile(True) else 1
        if value.get('tunnel_enabled'):
            import tunnel
            return 0 if tunnel.show_profile(True) else 1
        print('No remote provider is enabled. Run Setup Funnel.cmd first.');return 1
    except (OSError,RuntimeError,ValueError,KeyError) as exc:
        print(f'Remote profile error: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
