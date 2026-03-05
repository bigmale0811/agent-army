"""遊戲常數設定"""

# 牌靴設定
SHOE_DECKS = 8
RESHUFFLE_THRESHOLD = 0.2  # 剩餘牌數低於 20% 時重新洗牌

# 下注限制
MIN_BET = 10
MAX_BET = 5000
INITIAL_BALANCE = 10000

# 賠率表
PAYOUTS = {
    "banker": 0.95,       # 1:0.95（5% 抽水）
    "player": 1.0,        # 1:1
    "tie": 8.0,           # 1:8
    "banker_pair": 11.0,  # 1:11
    "player_pair": 11.0,  # 1:11
    "golden_three": 0.0,  # 規則待定
    "treasure_six": 0.0,  # 規則待定
}

# 下注倒數時間（秒）
BETTING_COUNTDOWN = 15

# WebSocket 設定
WS_HEARTBEAT_INTERVAL = 30
