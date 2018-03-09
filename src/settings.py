#!/usr/bin/env python3

from simple_settings import settings as store
import logging
import sys, argparse, os
import json

logger = logging.getLogger("settings")

settings = None
