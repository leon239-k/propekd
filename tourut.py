import asyncio
import re
import random
from datetime import datetime, timezone
from telethon import TelegramClient, Button, events
from telethon.tl.types import MessageEntityMention

API_ID = 28978042
API_HASH = '7c0e409c42833d73bfa096b09a5ec0b8'
BOT_TOKEN = '8228360696:AAFvLQjc8UtW70IqP1S71-TE1FyHvz-FtoE'

ADMIN_USERNAMES = ['redhack69', 'god_x_pawan']
LOG_GROUP_ID = -1002828913728
MONGO_URI = 'mongodb+srv://nzjzm7197:boss239k@cluster0.foyp3ff.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
MAX_VOTES_PER_USER = 12
FIXED_BUDGET = 500  # Fixed budget for all teams

# CHANGE THIS DATABASE NAME AS NEEDED
DATABASE_NAME = "vote_bot_new"

class VoteSession:
    def __init__(self, db_instance):
        self.db = db_instance  # Pass the Database instance
        self.voters = set()
        self.session_id = "current_session"  # Fixed session ID for persistence
        self.load_voters()
    
    def load_voters(self):
        """Load voters from database"""
        try:
            if self.db.db is None:
                print("⚠️ Database not connected - using in-memory storage")
                return
            
            voters_data = self.db.voters.find_one({'session_id': self.session_id})
            if voters_data and 'voters' in voters_data:
                self.voters = set(voters_data['voters'])
                print(f"✅ Loaded {len(self.voters)} voters from database")
                print(f"✅ Voters: {list(self.voters)}")
            else:
                print("ℹ️ No voters found in database, starting fresh")
        except Exception as e:
            print(f"❌ Error loading voters: {e}")
    
    def save_voters(self):
        """Save voters to database"""
        try:
            if self.db.db is None:
                print("⚠️ Cannot save voters - database not connected")
                return
            
            result = self.db.voters.update_one(
                {'session_id': self.session_id},
                {
                    '$set': {
                        'voters': list(self.voters),
                        'last_updated': datetime.now(timezone.utc),
                        'total_voters': len(self.voters)
                    }
                },
                upsert=True
            )
            print(f"✅ Saved {len(self.voters)} voters to database")
            print(f"✅ MongoDB result: matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_id is not None}")
        except Exception as e:
            print(f"❌ Error saving voters: {e}")
    
    def add_voters(self, usernames):
        added_count = 0
        for username in usernames:
            if username and username not in self.voters:
                self.voters.add(username.lower())
                added_count += 1
        
        if added_count > 0:
            self.save_voters()  # Save to database after adding
            print(f"✅ Added {added_count} new voters: {usernames}")
            print(f"✅ Total voters now: {len(self.voters)}")
        else:
            print("⚠️ No new voters added")
    
    def clear_voters(self):
        voter_count = len(self.voters)
        self.voters.clear()
        try:
            if self.db.db is not None:
                self.db.voters.delete_many({'session_id': self.session_id})
                print(f"✅ Cleared {voter_count} voters from database")
            else:
                print("⚠️ Database not connected, cleared from memory only")
        except Exception as e:
            print(f"❌ Error clearing voters: {e}")
    
    def get_voters(self):
        return list(self.voters)
    
    def is_valid_voter(self, username):
        return username and username.lower() in self.voters
    
    def is_valid_candidate(self, username):
        return username and username.lower() in self.voters
    
    def get_candidates(self, exclude_username=None):
        candidates = list(self.voters)
        if exclude_username:
            exclude_lower = exclude_username.lower()
            candidates = [candidate for candidate in candidates if candidate != exclude_lower]
        return candidates

class AuctionSession:
    def __init__(self, db_instance):
        self.db = db_instance
        self.load_data()
    
    def load_data(self):
        """Load auction data from database"""
        try:
            if self.db.db is None:
                print("⚠️ Database not connected - using in-memory auction storage")
                self.players = {}
                self.selected_players = {}
                self.sold_players = {}
                self.unsold_players = {}
                self.team_budgets = {}
                self.team_captains = {}
                self.captain_teams = {}
                self.current_auction_player = {}
                self.auction_mode_groups = {}
                self.allowed_group_ids = set()
                return
            
            # Load allowed groups
            groups_data = self.db.auction_groups.find_one({})
            if groups_data and 'allowed_groups' in groups_data:
                self.allowed_group_ids = set(groups_data['allowed_groups'])
            else:
                self.allowed_group_ids = set()
            
            # Load auction data for each group
            self.players = {}
            self.selected_players = {}
            self.sold_players = {}
            self.unsold_players = {}
            self.team_budgets = {}
            self.team_captains = {}
            self.captain_teams = {}
            self.current_auction_player = {}
            self.auction_mode_groups = {}
            
            auction_data = self.db.auction_data.find({})
            for data in auction_data:
                chat_id = data['chat_id']
                self.players[chat_id] = data.get('players', [])
                self.selected_players[chat_id] = set(data.get('selected_players', []))
                self.sold_players[chat_id] = data.get('sold_players', {})
                self.unsold_players[chat_id] = set(data.get('unsold_players', []))
                self.team_budgets[chat_id] = data.get('team_budgets', {})
                self.team_captains[chat_id] = data.get('team_captains', {})
                self.captain_teams[chat_id] = data.get('captain_teams', {})
                self.current_auction_player[chat_id] = data.get('current_auction_player')
                self.auction_mode_groups[chat_id] = data.get('auction_mode', False)
            
            print(f"✅ Loaded auction data for {len(self.players)} groups")
            
        except Exception as e:
            print(f"❌ Error loading auction data: {e}")
            self.players = {}
            self.selected_players = {}
            self.sold_players = {}
            self.unsold_players = {}
            self.team_budgets = {}
            self.team_captains = {}
            self.captain_teams = {}
            self.current_auction_player = {}
            self.auction_mode_groups = {}
            self.allowed_group_ids = set()
    
    def save_auction_data(self, chat_id):
        """Save auction data for specific chat to database"""
        try:
            if self.db.db is None:
                return
            
            self.db.auction_data.update_one(
                {'chat_id': chat_id},
                {
                    '$set': {
                        'players': self.players.get(chat_id, []),
                        'selected_players': list(self.selected_players.get(chat_id, set())),
                        'sold_players': self.sold_players.get(chat_id, {}),
                        'unsold_players': list(self.unsold_players.get(chat_id, set())),
                        'team_budgets': self.team_budgets.get(chat_id, {}),
                        'team_captains': self.team_captains.get(chat_id, {}),
                        'captain_teams': self.captain_teams.get(chat_id, {}),
                        'current_auction_player': self.current_auction_player.get(chat_id),
                        'auction_mode': self.auction_mode_groups.get(chat_id, False),
                        'last_updated': datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"❌ Error saving auction data for chat {chat_id}: {e}")
    
    def save_allowed_groups(self):
        """Save allowed groups to database"""
        try:
            if self.db.db is None:
                return
            
            self.db.auction_groups.update_one(
                {},
                {
                    '$set': {
                        'allowed_groups': list(self.allowed_group_ids),
                        'last_updated': datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
        except Exception as e:
            print(f"❌ Error saving allowed groups: {e}")
    
    def add_allowed_group(self, chat_id):
        self.allowed_group_ids.add(chat_id)
        self.save_allowed_groups()
    
    def remove_allowed_group(self, chat_id):
        if chat_id in self.allowed_group_ids:
            self.allowed_group_ids.remove(chat_id)
            self.save_allowed_groups()
    
    def is_group_allowed(self, chat_id):
        return chat_id in self.allowed_group_ids
    
    def is_captain(self, chat_id, username):
        return chat_id in self.captain_teams and username in self.captain_teams[chat_id]
    
    def clear_auction_data(self, chat_id):
        """Clear all auction data for a specific chat"""
        try:
            # Clear in-memory data
            if chat_id in self.players:
                del self.players[chat_id]
            if chat_id in self.selected_players:
                del self.selected_players[chat_id]
            if chat_id in self.sold_players:
                del self.sold_players[chat_id]
            if chat_id in self.unsold_players:
                del self.unsold_players[chat_id]
            if chat_id in self.team_budgets:
                del self.team_budgets[chat_id]
            if chat_id in self.team_captains:
                del self.team_captains[chat_id]
            if chat_id in self.captain_teams:
                del self.captain_teams[chat_id]
            if chat_id in self.current_auction_player:
                del self.current_auction_player[chat_id]
            if chat_id in self.auction_mode_groups:
                del self.auction_mode_groups[chat_id]
            
            # Clear from database
            if self.db.db is not None:
                self.db.auction_data.delete_one({'chat_id': chat_id})
            
            print(f"✅ Cleared auction data for chat {chat_id}")
            return True
        except Exception as e:
            print(f"❌ Error clearing auction data for chat {chat_id}: {e}")
            return False

class Database:
    def __init__(self, db_name):
        from pymongo import MongoClient
        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
            # Test the connection
            self.client.admin.command('ping')
            self.db = self.client[db_name]
            self.votes = self.db.votes
            self.leaderboard = self.db.leaderboard
            self.voters = self.db.voters
            self.auction_data = self.db.auction_data
            self.auction_groups = self.db.auction_groups
            print(f"✅ Database '{db_name}' connected successfully")
            
            # Print database info
            print(f"✅ Database collections: {self.db.list_collection_names()}")
            
            # Load existing leaderboard data for in-memory fallback
            self.leaderboard_data = {}
            if self.db is not None:
                all_leaderboard = self.leaderboard.find()
                for player in all_leaderboard:
                    self.leaderboard_data[player['username']] = {
                        'votes_received': player['votes_received']
                    }
                print(f"✅ Loaded {len(self.leaderboard_data)} players from leaderboard")
            
            # Print some stats
            votes_count = self.votes.count_documents({})
            leaderboard_count = self.leaderboard.count_documents({})
            print(f"📊 Database stats: {votes_count} votes, {leaderboard_count} leaderboard entries")
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            self.votes_data = []
            self.leaderboard_data = {}
            self.db = None
    
    def create_vote(self, voter_username, voted_for_username, vote_session='default'):
        if self.db is None:
            vote_id = f"{voter_username}_{voted_for_username}_{vote_session}"
            if any(vote_id == f"{v['voter']}_{v['voted_for']}_{v['session']}" for v in self.votes_data):
                raise ValueError("Already voted for this player")
            
            self.votes_data.append({
                'voter': voter_username.lower(),
                'voted_for': voted_for_username.lower(),
                'session': vote_session,
                'timestamp': datetime.now(timezone.utc)
            })
            return vote_id
        
        vote_data = {
            'voter_username': voter_username.lower(),
            'voted_for_username': voted_for_username.lower(),
            'vote_session': vote_session,
            'timestamp': datetime.now(timezone.utc)
        }
        
        try:
            result = self.votes.insert_one(vote_data)
            print(f"✅ Vote saved: {voter_username} -> {voted_for_username}")
            return result.inserted_id
        except Exception as e:
            print(f"❌ Vote save error: {e}")
            if 'duplicate' in str(e).lower():
                raise ValueError("Already voted for this player")
            raise ValueError("Error recording vote")
    
    def get_user_vote_count(self, voter_username, vote_session='default'):
        if self.db is None:
            return len([v for v in self.votes_data if v['voter'] == voter_username.lower() and v['session'] == vote_session])
        
        return self.votes.count_documents({
            'voter_username': voter_username.lower(),
            'vote_session': vote_session
        })
    
    def has_voted_for_player(self, voter_username, voted_for_username, vote_session='default'):
        if self.db is None:
            return any(v['voter'] == voter_username.lower() and 
                      v['voted_for'] == voted_for_username.lower() and 
                      v['session'] == vote_session for v in self.votes_data)
        
        vote = self.votes.find_one({
            'voter_username': voter_username.lower(),
            'voted_for_username': voted_for_username.lower(),
            'vote_session': vote_session
        })
        return vote is not None
    
    def get_user_votes(self, voter_username, vote_session='default'):
        if self.db is None:
            return [v['voted_for'] for v in self.votes_data if v['voter'] == voter_username.lower() and v['session'] == vote_session]
        
        votes = self.votes.find({
            'voter_username': voter_username.lower(),
            'vote_session': vote_session
        })
        return [vote['voted_for_username'] for vote in votes]
    
    def update_leaderboard(self, username):
        """Update leaderboard with proper vote counting"""
        if self.db is None:
            if username not in self.leaderboard_data:
                self.leaderboard_data[username] = {'votes_received': 0}
            self.leaderboard_data[username]['votes_received'] += 1
            print(f"✅ In-memory leaderboard updated for @{username}")
            return
        
        try:
            # Count actual votes for this user
            actual_votes = self.votes.count_documents({
                'voted_for_username': username.lower(),
                'vote_session': self.vote_session.session_id
            })
            
            # Update leaderboard with actual count
            result = self.leaderboard.update_one(
                {'username': username.lower()},
                {
                    '$set': {
                        'votes_received': actual_votes,
                        'last_updated': datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
            
            if result.upserted_id:
                print(f"✅ Created leaderboard entry for @{username} with {actual_votes} votes")
            else:
                print(f"✅ Updated leaderboard for @{username} to {actual_votes} votes")
                
        except Exception as e:
            print(f"❌ Error updating leaderboard for @{username}: {e}")
    
    def get_leaderboard(self, limit=16):
        if self.db is None:
            sorted_players = sorted(self.leaderboard_data.items(), 
                                  key=lambda x: x[1]['votes_received'], 
                                  reverse=True)
            return [{'username': k, 'votes_received': v['votes_received']} 
                   for k, v in sorted_players[:limit]]
        
        return list(self.leaderboard.find().sort('votes_received', -1).limit(limit))
    
    def get_user_stats(self, username):
        if self.db is None:
            return self.leaderboard_data.get(username, None)
        
        return self.leaderboard.find_one({'username': username.lower()})
    
    def get_user_rank(self, username):
        user = self.get_user_stats(username)
        if not user:
            return None
        
        if self.db is None:
            sorted_players = sorted(self.leaderboard_data.items(), 
                                  key=lambda x: x[1]['votes_received'], 
                                  reverse=True)
            for i, (player, _) in enumerate(sorted_players, 1):
                if player == username:
                    return i
            return None
        
        higher_count = self.leaderboard.count_documents({
            'votes_received': {'$gt': user['votes_received']}
        })
        return higher_count + 1

class VoteBot:
    def __init__(self):
        self.client = TelegramClient('vote_bot', API_ID, API_HASH)
        self.db = Database(DATABASE_NAME)
        self.vote_session = VoteSession(self.db)
        self.auction_session = AuctionSession(self.db)
        self.pending_votes = {}
        self.pending_auction_data = {}
    
    async def log_event(self, message):
        try:
            await self.client.send_message(LOG_GROUP_ID, f"📝 {message}")
        except:
            print(f"Log failed: {message}")
    
    async def is_admin(self, username):
        return username and username.lower() in [admin.lower() for admin in ADMIN_USERNAMES]
    
    def sanitize_username(self, username):
        return username.lstrip('@').lower().strip() if username else ""
    
    def parse_usernames(self, text):
        if not text:
            return []
        usernames = re.findall(r'@([a-zA-Z0-9_]+)', text)
        return [self.sanitize_username(username) for username in usernames if username]
    
    async def check_group_admin_or_owner(self, chat_id, user_id):
        try:
            participant = await self.client.get_permissions(chat_id, user_id)
            return participant.is_admin or participant.is_owner
        except:
            return False
    
    async def escape_markdown(self, text):
        """Escape markdown characters"""
        if not text:
            return ""
        escape_chars = r'\_*[]()~`>#+-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
    async def generate_slist_page(self, chat_id, page=1):
        """Generate slist content for a specific page"""
        current_sold_players = self.auction_session.sold_players.get(chat_id, {})
        current_team_budgets = self.auction_session.team_budgets.get(chat_id, {})
            
        teams_data = {}
        for team_name, budget in current_team_budgets.items():
            teams_data[team_name] = {
                "players": [], "total_spent": 0, "remaining_budget": budget, 
                "captain": self.auction_session.team_captains.get(chat_id, {}).get(team_name, "N/A")
            }

        grand_total_spent = 0
        for player, details in current_sold_players.items():
            team = details.get('team')
            price = details.get('price', 0)
            grand_total_spent += price
            if team in teams_data:
                teams_data[team]["players"].append({"name": player, "price": price})
                teams_data[team]["total_spent"] += price

        # Sort teams by team number
        sorted_team_names = sorted(teams_data.keys(), key=lambda x: int(x.replace('Team', '')) if x.replace('Team', '').isdigit() else x)
            
        # Split teams into pages (4 teams per page)
        teams_per_page = 4
        total_pages = max(1, (len(sorted_team_names) + teams_per_page - 1) // teams_per_page)
            
        # Validate page number
        page = max(1, min(page, total_pages))
            
        start_idx = (page - 1) * teams_per_page
        end_idx = start_idx + teams_per_page
        page_teams = sorted_team_names[start_idx:end_idx]

        # Build response with minimalist formatting
        response = "┌──────────────────────────────────────┐\n"          
        response += "│        AUCTION SUMMARY               │\n"
        response += "└──────────────────────────────────────┘\n\n"
            
        response += f"📊 TOTAL SPENT: {grand_total_spent:,}\n"
        response += f"📄 PAGE: {page}/{total_pages}\n\n"

        if not teams_data:
            response += "No teams have been set up yet."
        else:
            for team_name in page_teams:
                data = teams_data[team_name]
                team_name_escaped = await self.escape_markdown(team_name)
                captain_username = data['captain']
                captain_tag = f"@{captain_username}" if captain_username != 'N/A' else "N/A"
                remaining_budget_str = f"{data['remaining_budget']:,}" if isinstance(data['remaining_budget'], int) else await self.escape_markdown(str(data['remaining_budget']))

                response += "───────────────────────────────────────\n"
                response += f"TEAM {team_name_escaped.split('Team')[-1]} » {captain_tag}\n"
                response += "───────────────────────────────────────\n"
                response += f"Budget: {remaining_budget_str} | Spent: {data['total_spent']:,} | Players: {len(data['players'])}\n"
                    
                if data["players"]:
                    sorted_players = sorted(data["players"], key=lambda x: x.get('name', ''))
                    for player_info in sorted_players:
                        player_name_escaped = player_info.get('name', 'Unknown')
                        response += f"➤ {player_name_escaped} ({player_info.get('price', 0):,})\n"
                else:
                    response += "➤ No acquisitions yet\n"
                    
                response += "\n"

        # Create navigation buttons - SHOW ALL PAGE NUMBERS
        buttons = []
        if total_pages > 1:
            row = []
                
            # Show ALL page numbers
            for p in range(1, total_pages + 1):
                if p == page:
                    # Current page - highlighted
                    row.append(Button.inline(f"·{p}·", f"slist_page:{p}"))
                else:
                    # Other pages
                    row.append(Button.inline(str(p), f"slist_page:{p}"))
                
            buttons.append(row)

        return response, buttons

    async def setup_handlers(self):
        # Start command
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await event.reply(
                f'🤖 **Vote Bot**\n\n'
                f'**Database:** `{DATABASE_NAME}`\n'
                f'**Voters:** `{len(self.vote_session.get_voters())}`\n\n'
                '**Commands:** /vote /myvotes /leaderboard /stats\n'
                '**Admin:** /addvoters /showvoters /clearvoters\n\n'
                f'Vote for {MAX_VOTES_PER_USER} different players!'
            )
        # Sync all votes to leaderboard command
        @self.client.on(events.NewMessage(pattern='/sync_votes'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            try:
                if self.db.db is None:
                    await event.reply('❌ This command requires MongoDB connection')
                    return
                
                # Get all unique users who received votes
                pipeline = [
                    {"$group": {"_id": "$voted_for_username", "vote_count": {"$sum": 1}}}
                ]
                vote_counts = list(self.db.votes.aggregate(pipeline))
                
                synced_count = 0
                errors = []
                
                for item in vote_counts:
                    voted_user = item['_id']
                    actual_votes = item['vote_count']
                    
                    try:
                        # Update leaderboard to match actual votes
                        result = self.db.leaderboard.update_one(
                            {'username': voted_user},
                            {
                                '$set': {
                                    'votes_received': actual_votes,
                                    'last_updated': datetime.now(timezone.utc)
                                }
                            },
                            upsert=True
                        )
                        
                        if result.modified_count > 0 or result.upserted_id:
                            synced_count += 1
                            print(f"✅ Synced @{voted_user}: {actual_votes} votes")
                            
                    except Exception as e:
                        errors.append(f"@{voted_user}: {str(e)}")
                
                response = f'✅ Synced vote counts for {synced_count} users'
                if errors:
                    response += f'\n\n❌ Errors ({len(errors)}):\n' + '\n'.join(errors[:5])  # Show first 5 errors
                
                await event.reply(response)
                await self.log_event(f"Admin @{username} synced votes for {synced_count} users")
                
            except Exception as e:
                await event.reply(f'❌ Error syncing votes: {str(e)}')
                await self.log_event(f"Error in /sync_votes: {str(e)}")
                
        # Add voters command
        @self.client.on(events.NewMessage(pattern='/addvoters'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            usernames = self.parse_usernames(event.text)
            if not usernames:
                return await event.reply('❌ Use: /addvoters @user1 @user2')
            
            self.vote_session.add_voters(usernames)
            await self.log_event(f"Admin @{username} added voters: {', '.join(usernames)}")
            
            current_voters = self.vote_session.get_voters()
            await event.reply(f'✅ Added {len(usernames)} voters. Total: {len(current_voters)}')
        
        # Show voters command
        @self.client.on(events.NewMessage(pattern='/showvoters'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            voters = self.vote_session.get_voters()
            if not voters:
                return await event.reply('❌ No voters')
            
            voter_list = "\n".join([f"• @{voter}" for voter in voters])
            await event.reply(f'📋 Voters ({len(voters)}):\n{voter_list}')
        
        # Clear voters command
        @self.client.on(events.NewMessage(pattern='/clearvoters'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            self.vote_session.clear_voters()
            await self.log_event(f"Admin @{username} cleared all voters")
            await event.reply('✅ All voters cleared!')

        
        @self.client.on(events.NewMessage(pattern='/removevoter'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            usernames = self.parse_usernames(event.text)
            if not usernames:
                return await event.reply('❌ Use: /removevoter @username')
            
            removed = []
            for user in usernames:
                if user in self.vote_session.voters:
                    self.vote_session.voters.remove(user)
                    removed.append(user)
            
            if removed:
                self.vote_session.save_voters()  # Save changes to database
                await self.log_event(f"Admin @{username} removed voters: {', '.join(removed)}")
                await event.reply(f'✅ Removed {len(removed)} voters')
            else:
                await event.reply('❌ No voters found to remove')

        # Clear votes for particular player
        @self.client.on(events.NewMessage(pattern='/clearvotes'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            usernames = self.parse_usernames(event.text)
            if not usernames:
                return await event.reply('❌ Use: /clearvotes @username')
            
            cleared = []
            for user in usernames:
                # Remove from leaderboard
                if self.db.db is None:
                    # In-memory fallback
                    if user in self.db.leaderboard_data:
                        del self.db.leaderboard_data[user]
                        cleared.append(user)
                else:
                    result = self.db.leaderboard.delete_one({'username': user})
                    if result.deleted_count > 0:
                        cleared.append(user)
            
            if cleared:
                await self.log_event(f"Admin @{username} cleared votes for: {', '.join(cleared)}")
                await event.reply(f'✅ Cleared votes for {len(cleared)} players')
            else:
                await event.reply('❌ No votes found to clear')

        # Remove specific vote
        @self.client.on(events.NewMessage(pattern='/removevote'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            usernames = self.parse_usernames(event.text)
            if not usernames:
                return await event.reply('❌ Use: /removevote @voter @player (remove vote from player)')
            
            if len(usernames) < 2:
                return await event.reply('❌ Use: /removevote @voter @player')
            
            voter = usernames[0]
            player = usernames[1]
            
            # Remove specific vote
            if self.db.db is None:
                # In-memory fallback
                initial_count = len(self.db.votes_data)
                self.db.votes_data = [v for v in self.db.votes_data 
                                    if not (v['voter'] == voter and v['voted_for'] == player and v['session'] == self.vote_session.session_id)]
                removed = initial_count > len(self.db.votes_data)
            else:
                result = self.db.votes.delete_one({
                    'voter_username': voter,
                    'voted_for_username': player,
                    'vote_session': self.vote_session.session_id
                })
                removed = result.deleted_count > 0
            
            if removed:
                await self.log_event(f"Admin @{username} removed vote: @{voter} → @{player}")
                await event.reply(f'✅ Removed vote from @{voter} for @{player}')
            else:
                await event.reply('❌ Vote not found')

        # Show vote stats
        @self.client.on(events.NewMessage(pattern='/votestats'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            all_players = self.db.get_leaderboard(1000)  # Get all players
            total_votes = sum(player['votes_received'] for player in all_players)
            
            if not all_players:
                return await event.reply('📊 No votes recorded yet')
            
            text = "📊 **Vote Statistics**\n\n"
            text += f"**Total Votes Cast:** {total_votes}\n"
            text += f"**Total Players Voted For:** {len(all_players)}\n"
            text += f"**Total Voters:** {len(self.vote_session.get_voters())}\n\n"
            
            for player in all_players:
                text += f"• @{player['username']} - {player['votes_received']} votes\n"
            
            # Split message if too long
            if len(text) > 4000:
                parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
                for part in parts:
                    await event.reply(part)
            else:
                await event.reply(text)

        # Reset all data
        @self.client.on(events.NewMessage(pattern='/resetall'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            buttons = [
                [Button.inline("✅ YES Reset All", "confirm_reset"),
                Button.inline("❌ NO Cancel", "cancel_reset")]
            ]
            
            await event.reply(
                '⚠️ **DANGER ZONE** ⚠️\n\n'
                'This will reset:\n'
                '• All votes\n'
                '• Leaderboard\n'
                '• Voter list\n'
                '• All data\n\n'
                'Are you sure?',
                buttons=buttons
            )

        # Reset confirmation handler
        @self.client.on(events.CallbackQuery(pattern='confirm_reset'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.answer('❌ Not admin', alert=True)
            
            # Reset everything
            self.vote_session.clear_voters()
            
            if self.db.db is None:
                # In-memory reset
                self.db.votes_data.clear()
                self.db.leaderboard_data.clear()
            else:
                # MongoDB reset
                self.db.votes.delete_many({})
                self.db.leaderboard.delete_many({})
                self.db.voters.delete_many({})
            
            await self.log_event(f"🔄 Admin @{username} RESET ALL DATA")
            await event.edit('✅ **All data reset!**\nVotes, leaderboard, and voter list cleared.')
            await event.answer('Reset complete!', alert=True)

        @self.client.on(events.CallbackQuery(pattern='cancel_reset'))
        async def handler(event):
            await event.edit('❌ Reset cancelled.')
            await event.answer('Cancelled', alert=True)

        # My votes command - Show who user voted for
        @self.client.on(events.NewMessage(pattern='/myvotes'))
        async def handler(event):
            voter_username = event.sender.username
            if not voter_username:
                return await event.reply('❌ Set username first')
            
            sanitized_username = self.sanitize_username(voter_username)
            
            if not self.vote_session.is_valid_voter(sanitized_username):
                return await event.reply('❌ Not in voter list')
            
            user_votes = self.db.get_user_votes(sanitized_username, self.vote_session.session_id)
            vote_count = len(user_votes)
            
            if vote_count == 0:
                return await event.reply('📝 You haven\'t voted for anyone yet.\nUse /vote to start voting!')
            
            votes_list = "\n".join([f"• @{player}" for player in user_votes])
            await event.reply(
                f'📋 **Your Votes** ({vote_count}/{MAX_VOTES_PER_USER})\n\n'
                f'{votes_list}\n\n'
                f'Use /vote to vote for more players!'
            )

        @self.client.on(events.NewMessage(pattern='/vote'))
        async def handler(event):
            voter_username = event.sender.username
            if not voter_username:
                return await event.reply('❌ Set username first')
            
            sanitized_username = self.sanitize_username(voter_username)
            
            if not self.vote_session.is_valid_voter(sanitized_username):
                return await event.reply('❌ Not in voter list')
            
            votes_used = self.db.get_user_vote_count(sanitized_username, self.vote_session.session_id)
            
            if votes_used >= MAX_VOTES_PER_USER:
                return await event.reply(f'❌ You have used all {MAX_VOTES_PER_USER} votes!')
            
            votes_remaining = MAX_VOTES_PER_USER - votes_used
            
            user_votes = self.db.get_user_votes(sanitized_username, self.vote_session.session_id)
            all_candidates = self.vote_session.get_candidates(sanitized_username)
            
            # Create permanent numbering for all candidates
            permanent_numbered_candidates = []
            for i, candidate in enumerate(all_candidates, 1):
                permanent_numbered_candidates.append((i, candidate))
            
            # Filter out voted candidates but keep original numbers
            available_candidates = []
            for number, candidate in permanent_numbered_candidates:
                if candidate not in user_votes:
                    available_candidates.append((number, candidate))
            
            if not available_candidates:
                return await event.reply('❌ No more players available to vote for!')
            
            # Create buttons with original numbers (6 per row)
            buttons = []
            current_row = []
            for number, candidate in available_candidates:
                current_row.append(Button.inline(str(number), f"select:{candidate}:{event.sender_id}"))
                if len(current_row) == 6:
                    buttons.append(current_row)
                    current_row = []
            
            # Add any remaining buttons
            if current_row:
                buttons.append(current_row)
            
            buttons.append([Button.inline("📋 My Votes", "show_my_votes")])
            
            # Create player list with original numbers (showing gaps for voted players)
            player_list = "\n".join([f"{number}. @{candidate}" for number, candidate in available_candidates])
            
            await event.reply(
                f'🗳️ **Vote for Players**\n\n'
                f'Votes used: **{votes_used}/{MAX_VOTES_PER_USER}**\n'
                f'Votes remaining: **{votes_remaining}**\n\n'
                f'**Available Players:**\n{player_list}\n\n'
                f'Select a player number to vote:',
                buttons=buttons
            )
        
        @self.client.on(events.CallbackQuery(pattern=r'select:(.+):(\d+)'))
        async def handler(event):
            voter_username = event.sender.username
            selected_candidate = event.pattern_match.group(1).decode()
            original_user_id = int(event.pattern_match.group(2).decode())

            if event.sender_id != original_user_id:
                return await event.answer('❌ This vote menu is not for you! Use /vote first.', alert=True)

            if not voter_username:
                return await event.answer('❌ Set username first', alert=True)
            
            sanitized_voter = self.sanitize_username(voter_username)
            self.pending_votes[event.sender_id] = {
                'voter': sanitized_voter,
                'candidate': selected_candidate
            }
            
            buttons = [
                [Button.inline("✅ CONFIRM Vote", f"confirm_vote:{selected_candidate}:{original_user_id}"),
                Button.inline("❌ CANCEL", f"cancel_vote:{original_user_id}")]
            ]
            
            await event.edit(
                f'⚠️ **Confirm Your Vote** ⚠️\n\n'
                f'You are about to vote for:\n'
                f'**@{selected_candidate}**\n\n'
                f'This action cannot be undone!',
                buttons=buttons
            )

        # Vote confirmation - FIXED VERSION
        @self.client.on(events.CallbackQuery(pattern=r'confirm_vote:(.+):(\d+)'))
        async def handler(event):
            voter_username = event.sender.username
            voted_for = event.pattern_match.group(1).decode()
            original_user_id = int(event.pattern_match.group(2).decode())
            if not voter_username:
                return await event.answer('❌ Set username first', alert=True)
            if event.sender_id != original_user_id:
                return await event.answer('❌ This vote confirmation is not for you!', alert=True)

            sanitized_voter = self.sanitize_username(voter_username)
            
            # Simple validation
            if not self.vote_session.is_valid_voter(sanitized_voter):
                return await event.answer('❌ Not in voter list', alert=True)
            
            if self.db.has_voted_for_player(sanitized_voter, voted_for, self.vote_session.session_id):
                return await event.answer('❌ Already voted for this player', alert=True)
            
            if sanitized_voter == voted_for:
                return await event.answer('❌ Cannot self-vote', alert=True)
            
            votes_used = self.db.get_user_vote_count(sanitized_voter, self.vote_session.session_id)
            if votes_used >= MAX_VOTES_PER_USER:
                return await event.answer(f'❌ You have used all {MAX_VOTES_PER_USER} votes!', alert=True)
            
            # Record vote
            try:
                # 1. Save the vote first
                self.db.create_vote(sanitized_voter, voted_for, self.vote_session.session_id)
                
                # 2. Force update leaderboard with actual count
                if self.db.db is not None:
                    # Count actual votes for this user
                    actual_votes = self.db.votes.count_documents({
                        'voted_for_username': voted_for,
                        'vote_session': self.vote_session.session_id
                    })
                    
                    # Update leaderboard with actual count
                    self.db.leaderboard.update_one(
                        {'username': voted_for},
                        {
                            '$set': {
                                'votes_received': actual_votes,
                                'last_updated': datetime.now(timezone.utc)
                            }
                        },
                        upsert=True
                    )
                    print(f"✅ Leaderboard force updated: @{voted_for} now has {actual_votes} votes")
                else:
                    # In-memory fallback
                    self.db.update_leaderboard(voted_for)
                
                await self.log_event(f"🗳️ @{sanitized_voter} voted for @{voted_for}")
                await event.answer('✅ Vote recorded!', alert=True)
                
                votes_remaining = MAX_VOTES_PER_USER - (votes_used + 1)
                
                if votes_remaining > 0:
                    await event.edit(f'✅ **Vote Confirmed!**\n\nYou voted for: **@{voted_for}**\nVotes remaining: **{votes_remaining}**')
                else:
                    await event.edit(f'✅ **Vote Confirmed!**\n\nYou voted for: **@{voted_for}**\n🎉 **All votes used!**')
                
                if event.sender_id in self.pending_votes:
                    del self.pending_votes[event.sender_id]
                
            except Exception as e:
                print(f"VOTE ERROR: {e}")
                await event.answer('❌ Error recording vote. Please try /vote again.', alert=True)
                
        # Cancel vote
        @self.client.on(events.CallbackQuery(pattern=r'cancel_vote(\d+)'))
        async def handler(event):
            original_user_id = int(event.pattern_match.group(2).decode())
            
            if event.sender_id != original_user_id:
                return await event.answer('❌ This vote confirmation is not for you!', alert=True)
    
            if event.sender_id in self.pending_votes:
                del self.pending_votes[event.sender_id]

            await event.edit('❌ Vote cancelled.')
            await event.answer('Cancelled', alert=True)
        
        # My votes
        @self.client.on(events.CallbackQuery(pattern='show_my_votes'))
        async def handler(event):
            voter_username = event.sender.username
            if not voter_username:
                return await event.answer('❌ Set username first', alert=True)
            
            sanitized_username = self.sanitize_username(voter_username)
            user_votes = self.db.get_user_votes(sanitized_username, self.vote_session.session_id)
            vote_count = len(user_votes)
            
            if vote_count == 0:
                text = '📝 You haven\'t voted for anyone yet.'
            else:
                votes_list = "\n".join([f"• @{player}" for player in user_votes])
                text = f'📋 **Your Votes** ({vote_count}/{MAX_VOTES_PER_USER})\n\n{votes_list}'
            
            await event.answer(text, alert=True)
        
        # Leaderboard command
        @self.client.on(events.NewMessage(pattern='/leaderboard'))
        async def handler(event):
            top_players = self.db.get_leaderboard(16)
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin', alert=True)
            if not top_players:
                return await event.reply('📊 No votes yet')
            
            text = "🏆 **Top 16**\n\n"
            for i, player in enumerate(top_players, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                text += f"{medal} @{player['username']} - {player['votes_received']} votes\n"
            
            await event.reply(text)

        # Stats command - IMPROVED VERSION
        @self.client.on(events.NewMessage(pattern='/stats'))
        async def handler(event):
            username = event.sender.username
            if not username:
                return await event.reply('❌ Set username first')
            
            sanitized_username = self.sanitize_username(username)
            
            # Get votes received (count from votes collection)
            if self.db.db is None:
                # In-memory fallback
                votes_received = len([v for v in self.db.votes_data 
                                    if v['voted_for'] == sanitized_username and v['session'] == self.vote_session.session_id])
            else:
                votes_received = self.db.votes.count_documents({
                    'voted_for_username': sanitized_username,
                    'vote_session': self.vote_session.session_id
                })
            
            # Get leaderboard stats
            stats = self.db.get_user_stats(sanitized_username)
            
            # If no leaderboard entry but user has votes, create one
            if votes_received > 0 and not stats:
                # Create leaderboard entry
                if self.db.db is None:
                    if sanitized_username not in self.db.leaderboard_data:
                        self.db.leaderboard_data[sanitized_username] = {'votes_received': 0}
                    self.db.leaderboard_data[sanitized_username]['votes_received'] = votes_received
                    stats = self.db.leaderboard_data[sanitized_username]
                else:
                    self.db.leaderboard.update_one(
                        {'username': sanitized_username},
                        {
                            '$set': {
                                'votes_received': votes_received,
                                'last_updated': datetime.now(timezone.utc)
                            }
                        },
                        upsert=True
                    )
                    stats = self.db.get_user_stats(sanitized_username)
            
            if not stats and votes_received == 0:
                return await event.reply('📊 No votes received yet')
            
            # Get rank
            rank = self.db.get_user_rank(sanitized_username)
            
            # Use actual votes received count (might be more accurate than leaderboard)
            actual_votes = votes_received if votes_received > 0 else (stats['votes_received'] if stats else 0)
            
            await event.reply(
                f"📊 **Stats**\n"
                f"👤 @{username}\n"
                f"⭐ Votes Received: {actual_votes}\n"
                f"🏆 Rank: #{rank if rank else 'N/A'}"
            )
        
        # Test command to check database
        @self.client.on(events.NewMessage(pattern='/testdb'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            if self.db.db is None:
                await event.reply('❌ Database not connected')
            else:
                collections = self.db.db.list_collection_names()
                voters_count = self.db.voters.count_documents({})
                await event.reply(f'✅ DB Connected\nCollections: {collections}\nVoters docs: {voters_count}')

        # ==================== AUCTION HANDLERS ====================

        # Add chat to allowed groups
        @self.client.on(events.NewMessage(pattern='/add_chat'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            chat_id = event.chat_id
            self.auction_session.add_allowed_group(chat_id)
            await self.log_event(f"Admin @{username} added chat {chat_id} to auction groups")
            await event.reply(f'✅ Chat added to auction groups!')

        # Clear auction data command
        @self.client.on(events.NewMessage(pattern='/clearauction'))
        async def handler(event):
            username = event.sender.username
            if not await self.is_admin(username):
                return await event.reply('❌ Not admin')
            
            chat_id = event.chat_id
            if self.auction_session.clear_auction_data(chat_id):
                await self.log_event(f"Admin @{username} cleared auction data for chat {chat_id}")
                await event.reply('✅ Auction data cleared! Use /submit to start fresh.')
            else:
                await event.reply('❌ Error clearing auction data.')

        # Submit player list - UPDATED VERSION
        @self.client.on(events.NewMessage(pattern='/submit'))
        async def handler(event):
            chat_id = event.chat_id
            user_id = event.sender_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized. An admin must use /add_chat first.")
                    return

                if await self.check_group_admin_or_owner(chat_id, user_id):
                    command_text = event.text
                    match = re.match(r'/submit\s+(.*)', command_text, re.DOTALL | re.IGNORECASE)
                    if match:
                        player_list_text = match.group(1).strip()
                        if player_list_text:
                            submitted_players = [p.strip() for p in player_list_text.split('\n') if p.strip()]
                            if not submitted_players:
                                await event.reply("Player list seems empty after processing. Please provide player names, one per line.")
                                return

                            # Reset state IN MEMORY for a new auction setup
                            self.auction_session.players[chat_id] = submitted_players
                            self.auction_session.selected_players[chat_id] = set()
                            self.auction_session.sold_players[chat_id] = {}
                            self.auction_session.unsold_players[chat_id] = set()
                            self.auction_session.team_budgets[chat_id] = {}
                            self.auction_session.team_captains[chat_id] = {}
                            self.auction_session.captain_teams[chat_id] = {}
                            self.auction_session.current_auction_player[chat_id] = None
                            self.auction_session.auction_mode_groups[chat_id] = False

                            self.auction_session.save_auction_data(chat_id)

                            # CHANGED: Now ask for captains directly, no team budgets
                            await event.reply(
                                f"✅ {len(submitted_players)} players submitted successfully!\n\n"
                                f"💰 **Fixed Budget:** {FIXED_BUDGET} for all teams\n\n"
                                "Now please provide captain usernames (one per line, must start with '@'):\n\n"
                                "@captain1\n@captain2\n@captain3\n..."
                            )
                            self.pending_auction_data[event.sender_id] = {'step': 'captains_only', 'chat_id': chat_id,'user_id':user_id}
                        else:
                            await event.reply("Please provide a non-empty list of players after the /submit command, one player per line.")
                    else:
                        await event.reply("Invalid format. Use: `/submit Player One\nPlayer Two\nPlayer Three`")
                else:
                    await event.reply("❌ You are not authorized to submit a player list.")

            except Exception as e:
                await self.log_event(f"Error in /submit: {str(e)}")
                await event.reply("An unexpected error occurred processing the player list.")

        # Process captains only - NEW HANDLER
        @self.client.on(events.NewMessage(func=lambda e: e.sender_id in self.pending_auction_data and self.pending_auction_data[e.sender_id]['step'] == 'captains_only'))
        async def handler(event):
            chat_id = self.pending_auction_data[event.sender_id]['chat_id']
            user_id = self.pending_auction_data[event.sender_id]['user_id']
            if event.sender_id != user_id:
                return

            try:
                lines = event.text.strip().split("\n")
                captains = []
                errors = []

                for line in lines:
                    line = line.strip()
                    if not line: 
                        continue
                    
                    if line.startswith("@"):
                        captain_username = line[1:].lower().strip()
                        if not captain_username:
                            errors.append(f"Empty username after '@' in: '{line}'")
                            continue
                        
                        if captain_username in captains:
                            errors.append(f"Duplicate captain: '@{captain_username}'")
                            continue
                        
                        captains.append(captain_username)
                    else:
                        errors.append(f"Invalid format (must start with '@'): '{line}'")

                if errors:
                    error_message = "Errors found while processing captains:\n- " + "\n- ".join(errors)
                    error_message += "\n\nPlease correct the errors and provide the list again (one @username per line):"
                    await event.reply(error_message)
                    return

                if captains:
                    # Create teams automatically with fixed budget
                    team_budgets = {}
                    team_captains = {}
                    captain_teams = {}
                    
                    for i, captain in enumerate(captains, 1):
                        team_name = f"Team{i}"
                        team_budgets[team_name] = FIXED_BUDGET
                        team_captains[team_name] = captain
                        captain_teams[captain] = team_name

                    # Save to auction session
                    self.auction_session.team_budgets[chat_id] = team_budgets
                    self.auction_session.team_captains[chat_id] = team_captains
                    self.auction_session.captain_teams[chat_id] = captain_teams
                    self.auction_session.save_auction_data(chat_id)

                    # Create summary message
                    summary = f"✅ **Auction Setup Complete!** ✅\n\n"
                    summary += f"**Players:** {len(self.auction_session.players[chat_id])}\n"
                    summary += f"**Teams:** {len(captains)}\n"
                    summary += f"**Budget per Team:** {FIXED_BUDGET:,}\n\n"
                    summary += "**Team Assignments:**\n"
                    
                    for team_name, captain in team_captains.items():
                        summary += f"• {team_name}: @{captain}\n"
                    
                    summary += f"\n🎉 Ready to start! Use `/next` to select a player and `/auction on` to start bidding."

                    await event.reply(summary)
                    del self.pending_auction_data[event.sender_id]
                    
                    await self.log_event(f"Auction setup completed in chat {chat_id} with {len(captains)} teams")

                else:
                    await event.reply("No valid captains provided. Please try again with usernames starting with '@' on each line.")

            except Exception as e:
                await self.log_event(f"Error processing captains: {str(e)}")
                await event.reply(f"An unexpected error occurred: {str(e)}\nPlease try again with usernames starting with '@' on each line.")

        # Enable/disable auction mode
        @self.client.on(events.NewMessage(pattern='/auction'))
        async def handler(event):
            chat_id = event.chat_id
            user_id = event.sender_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized. Use /add_chat first.")
                    return

                command_text = event.text.split()
                if len(command_text) > 1:
                    mode = command_text[1].lower()

                    if await self.check_group_admin_or_owner(chat_id, user_id):
                        if mode == "on":
                            if not self.auction_session.players.get(chat_id) or not self.auction_session.team_budgets.get(chat_id) or not self.auction_session.team_captains.get(chat_id):
                                await event.reply("❌ Cannot turn auction ON. Setup is incomplete. Use /submit first.")
                                return

                            self.auction_session.auction_mode_groups[chat_id] = True
                            self.auction_session.save_auction_data(chat_id)
                            await event.reply("⚠️ Auction mode is now ON ⚠️\n\nOnly numeric bids from captains are allowed. Other messages will be deleted.\nAdmins: Use `.` for countdown, `/next` for players, `/sold` or `/unsold` to conclude.")
                            await self.log_event(f"Auction mode turned ON in group {chat_id} by user {user_id}")
                        elif mode == "off":
                            self.auction_session.auction_mode_groups[chat_id] = False
                            self.auction_session.save_auction_data(chat_id)
                            await event.reply("✅ Auction mode is now OFF. Normal conversation is allowed.")
                            await self.log_event(f"Auction mode turned OFF in group {chat_id} by user {user_id}")
                        else:
                            await event.reply("Invalid auction mode. Use `/auction on` or `/auction off`.")
                    else:
                        await event.reply("❌ You are not authorized to change auction mode.")
                else:
                    current_mode = 'ON' if self.auction_session.auction_mode_groups.get(chat_id, False) else 'OFF'
                    await event.reply(f"Current auction mode: {current_mode}. Use `/auction on` or `/auction off` to change.")

            except Exception as e:
                await self.log_event(f"Error in /auction: {str(e)}")
                await event.reply("An unexpected error occurred.")

        # Select next player
        @self.client.on(events.NewMessage(pattern='/next'))
        async def handler(event):
            chat_id = event.chat_id
            user_id = event.sender_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized. Use /add_chat first.")
                    return

                if chat_id not in self.auction_session.players or not self.auction_session.players.get(chat_id):
                    await event.reply("No player list found in memory. Use /submit first.")
                    return

                if not await self.check_group_admin_or_owner(chat_id, user_id):
                    await event.reply("❌ You are not authorized to select players.")
                    return

                sold_set = set(self.auction_session.sold_players.get(chat_id, {}).keys())
                unsold_set = self.auction_session.unsold_players.get(chat_id, set())
                all_submitted_players = set(self.auction_session.players.get(chat_id, []))

                available_players = list(all_submitted_players - sold_set - unsold_set)

                if not available_players:
                    await event.reply("🎉 All players have been auctioned (sold or unsold).")
                    self.auction_session.current_auction_player[chat_id] = None
                    self.auction_session.save_auction_data(chat_id)
                    return

                player_to_auction = random.choice(available_players)
                self.auction_session.current_auction_player[chat_id] = player_to_auction
                self.auction_session.save_auction_data(chat_id)

                player_display = await self.escape_markdown(player_to_auction)
                await event.reply(f" Bidding Open For 👇\n\n🎯 Player: **{player_to_auction}**\n\nCaptains, place your bids!")
                await self.log_event(f"Player {player_to_auction} selected for auction in group {chat_id}")

            except Exception as e:
                await self.log_event(f"Error in /next: {str(e)}")
                await event.reply("An unexpected error occurred.")
                
        # Mark player as sold
        @self.client.on(events.NewMessage(pattern='/sold'))
        async def handler(event):
            chat_id = event.chat_id
            user_id = event.sender_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized.")
                    return

                if not await self.check_group_admin_or_owner(chat_id, user_id):
                    await event.reply("❌ You are not authorized to mark players as sold.")
                    return

                if not event.reply_to_msg_id:
                    await event.reply("⚠️ Please use `/sold` by *replying* to the winning bid message.")
                    return

                player_being_auctioned = self.auction_session.current_auction_player.get(chat_id)
                if not player_being_auctioned:
                    await event.reply("❓ No player is currently selected for auction in memory. Use `/next` first.")
                    return

                # Ensure structures exist in memory
                self.auction_session.sold_players.setdefault(chat_id, {})
                self.auction_session.team_budgets.setdefault(chat_id, {})
                self.auction_session.captain_teams.setdefault(chat_id, {})

                command_parts = event.text.split(' ', 1)
                custom_message = command_parts[1].strip() if len(command_parts) > 1 else ""

                replied_message = await event.get_reply_message()
                bidder_user = await replied_message.get_sender()
                bidder_username = bidder_user.username
                bidder_display_name = f"@{bidder_username}" if bidder_username else f"{bidder_user.first_name}"

                try:
                    bid_amount = int(replied_message.text.strip().replace(',', ''))
                    if bid_amount < 0: raise ValueError("Bid cannot be negative")
                except (ValueError, TypeError):
                    await event.reply("❌ Invalid bid message. Please reply to a message containing only the numeric bid amount.")
                    return

                team_name = None
                # Check captaincy
                if bidder_username and self.auction_session.is_captain(chat_id, bidder_username.lower()):
                    if chat_id in self.auction_session.captain_teams and bidder_username.lower() in self.auction_session.captain_teams[chat_id]:
                        team_name = self.auction_session.captain_teams[chat_id][bidder_username.lower()]
                    else:
                        await event.reply(f"⚠️ Internal data inconsistency for captain @{bidder_username}. Cannot process sale.")
                        return
                else:
                    bidder_display_name_escaped = await self.escape_markdown(bidder_display_name)
                    await event.reply(f"⚠️ Bidder {bidder_display_name_escaped} is not a registered captain in this auction.")
                    return

                if chat_id not in self.auction_session.team_budgets or team_name not in self.auction_session.team_budgets[chat_id]:
                    await event.reply(f"⚠️ Internal data inconsistency: Budget not found for team '{team_name}'. Cannot process sale.")
                    return

                current_budget = self.auction_session.team_budgets[chat_id][team_name]
                if bid_amount > current_budget:
                    team_name_escaped = await self.escape_markdown(team_name)
                    player_being_auctioned_escaped = await self.escape_markdown(player_being_auctioned)
                    await event.reply(f"📉 Insufficient funds! Team '**{team_name_escaped}**' only has {current_budget:,} remaining (Bid: {bid_amount:,}). Player **{player_being_auctioned_escaped}** remains unsold for now.")
                    return

                # Record the sale
                self.auction_session.sold_players[chat_id][player_being_auctioned] = {
                    'price': bid_amount,
                    'buyer': bidder_display_name,
                    'buyer_id': bidder_user.id,
                    'buyer_username': bidder_username,
                    'team': team_name
                }
                self.auction_session.team_budgets[chat_id][team_name] -= bid_amount
                remaining_budget = self.auction_session.team_budgets[chat_id][team_name]
                self.auction_session.current_auction_player[chat_id] = None

                self.auction_session.save_auction_data(chat_id)

                # Create confirmation message
                player_escaped = player_being_auctioned
                team_name_escaped = await self.escape_markdown(team_name)
                bidder_display_name_escaped = await self.escape_markdown(bidder_display_name)
                custom_message_escaped = await self.escape_markdown(custom_message)

                sold_message_text = f" **SOLD!**✔️ \n\n"
                sold_message_text += f"Player: **{player_escaped}**\n"
                sold_message_text += f"To: **{team_name_escaped}** ({bidder_display_name_escaped})\n"
                sold_message_text += f"For: **{bid_amount:,}**\n"
                if custom_message_escaped:
                    sold_message_text += f"Comment: {custom_message_escaped}\n"
                sold_message_text += f"\n Team '**{team_name_escaped}**' remaining budget: {remaining_budget:,}"

                team_players_info = []
                team_total_spent = 0
                for p, info in self.auction_session.sold_players.get(chat_id, {}).items():
                    if info.get('team') == team_name:
                        team_players_info.append(f"   ➥ {p} ({info.get('price', 0):,})")
                        team_total_spent += info.get('price', 0)

                if team_players_info:
                    team_players_info.sort()
                    sold_message_text += f"\n\nPlayers bought by **{team_name_escaped}** ({len(team_players_info)} total, spent {team_total_spent:,}):\n"
                    sold_message_text += "\n".join(team_players_info)

                sold_reply = await replied_message.reply(sold_message_text)
                await self.log_event(f"Player {player_being_auctioned} sold to team {team_name} for {bid_amount} in group {chat_id}")

                # Try pinning the sold message
                try:
                    await self.client.pin_message(chat_id, sold_reply, notify=False)
                    await self.log_event(f"Pinned sold message in chat {chat_id}")
                except Exception as pin_error:
                    await self.log_event(f"Could not pin message in chat {chat_id}: {pin_error}")

            except Exception as e:
                await self.log_event(f"Error in /sold: {str(e)}")
                await event.reply(f"❌ An unexpected error occurred processing the sale.")

        # Mark player as unsold
        @self.client.on(events.NewMessage(pattern='/unsold'))
        async def handler(event):
            chat_id = event.chat_id
            user_id = event.sender_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized.")
                    return

                if not await self.check_group_admin_or_owner(chat_id, user_id):
                    await event.reply("❌ You are not authorized to mark players as unsold.")
                    return

                # Initialize if needed
                self.auction_session.unsold_players.setdefault(chat_id, set())
                self.auction_session.players.setdefault(chat_id, [])
                self.auction_session.sold_players.setdefault(chat_id, {})

                command_parts = event.text.split(' ', 1)
                player_name_arg = command_parts[1].strip() if len(command_parts) > 1 else None

                player_to_mark_unsold = None

                if player_name_arg:
                    found_player = None
                    submitted_players_list = self.auction_session.players.get(chat_id, [])
                    for p in submitted_players_list:
                        if p.strip().lower() == player_name_arg.lower():
                            found_player = p.strip()
                            break

                    if found_player:
                        if found_player in self.auction_session.sold_players.get(chat_id, {}):
                            player_escaped = await self.escape_markdown(found_player)
                            await event.reply(f"⚠️ Player '**{player_escaped}**' is currently marked as SOLD in memory. Cannot mark as unsold directly.")
                            return
                        if found_player in self.auction_session.unsold_players.get(chat_id, set()):
                            player_escaped = await self.escape_markdown(found_player)
                            await event.reply(f"ℹ️ Player '**{player_escaped}**' is already marked as UNSOLD in memory.")
                            return
                        player_to_mark_unsold = found_player
                    else:
                        player_name_arg_escaped = await self.escape_markdown(player_name_arg)
                        await event.reply(f"❓ Player '**{player_name_arg_escaped}**' not found in the original player list for this group.")
                        return
                else:
                    player_to_mark_unsold = self.auction_session.current_auction_player.get(chat_id)
                    if not player_to_mark_unsold:
                        await event.reply("❓ No player is currently selected for auction in memory. Use `/next` first, or specify a player name like `/unsold Player Name`.")
                        return

                # Update state
                self.auction_session.unsold_players[chat_id].add(player_to_mark_unsold)

                # Remove from sold if it was there
                if player_to_mark_unsold in self.auction_session.sold_players.get(chat_id, {}):
                    del self.auction_session.sold_players[chat_id][player_to_mark_unsold]

                # Clear current player only if it was the one being marked unsold
                if self.auction_session.current_auction_player.get(chat_id) == player_to_mark_unsold:
                    self.auction_session.current_auction_player[chat_id] = None

                self.auction_session.save_auction_data(chat_id)
                player_escaped = await self.escape_markdown(player_to_mark_unsold)
                await event.reply(f"➖ Player **{player_escaped}** marked as UNSOLD.")
                await self.log_event(f"Player {player_to_mark_unsold} marked as unsold in group {chat_id} by user {user_id}")

            except Exception as e:
                await self.log_event(f"Error in /unsold: {str(e)}")
                await event.reply("An unexpected error occurred.")

        # Show sold players list
        @self.client.on(events.NewMessage(pattern='/summary'))
        async def handler(event):
            chat_id = event.chat_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized.")
                    return

                current_sold_players = self.auction_session.sold_players.get(chat_id, {})
                current_team_budgets = self.auction_session.team_budgets.get(chat_id, {})

                if not current_team_budgets:
                    await event.reply("No teams & budgets found in memory for this group. Use /submit first to set up.")
                    return

                # Generate the slist message for page 1
                response, buttons = await self.generate_slist_page(chat_id, 1)
                
                if buttons:
                    await event.reply(response, buttons=buttons)
                else:
                    await event.reply(response)

            except Exception as e:
                await self.log_event(f"Error in /slist: {str(e)}")
                await event.reply("An unexpected error occurred.")

        
        # Add callback handler for pagination
        @self.client.on(events.CallbackQuery(pattern='slist_page:(.+)'))
        async def slist_page_handler(event):
            try:
                page = int(event.pattern_match.group(1).decode())
                chat_id = event.chat_id
                
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.answer("This group is not authorized.", alert=True)
                    return

                current_team_budgets = self.auction_session.team_budgets.get(chat_id, {})
                if not current_team_budgets:
                    await event.answer("No auction data found.", alert=True)
                    return

                # Generate the updated message
                response, buttons = await self.generate_slist_page(chat_id, page)
                
                await event.edit(response, buttons=buttons)
                await event.answer()

            except Exception as e:
                await self.log_event(f"Error in slist pagination: {str(e)}")
                await event.answer("Error loading page.", alert=True)
                
        @self.client.on(events.NewMessage(pattern='/myteam'))
        async def handler(event):
            chat_id = event.chat_id
            user_id = event.sender_id
            username = event.sender.username

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized.")
                    return

                if not username:
                    await event.reply("❌ You need a username to use this command.")
                    return

                # Check if user is a captain
                if not self.auction_session.is_captain(chat_id, username.lower()):
                    await event.reply("❌ You are not a captain in this auction.")
                    return

                # Get team details for this captain
                team_name = self.auction_session.captain_teams.get(chat_id, {}).get(username.lower())
                if not team_name:
                    await event.reply("❌ Team not found for your captain profile.")
                    return

                # Get team data
                team_budget = self.auction_session.team_budgets.get(chat_id, {}).get(team_name, 0)
                sold_players = self.auction_session.sold_players.get(chat_id, {})
                
                # Filter players for this team
                team_players = []
                total_spent = 0
                for player, details in sold_players.items():
                    if details.get('team') == team_name:
                        team_players.append({
                            'name': player,
                            'price': details.get('price', 0),
                            'buyer': details.get('buyer', 'Unknown')
                        })
                        total_spent += details.get('price', 0)

                # Build team summary
                response = "┌──────────────────────────────────────┐\n"
                response += "│           MY TEAM SUMMARY            │\n"
                response += "└──────────────────────────────────────┘\n\n"
                
                response += f" TEAM: {team_name}\n"
                response += f"👤 CAPTAIN: @{username}\n\n"
                
                response += "───────────────────────────────────────\n"
                response += "💰 FINANCIAL OVERVIEW\n"
                response += "───────────────────────────────────────\n"
                response += f"Initial Budget: {FIXED_BUDGET:,}\n"
                response += f"Total Spent: {total_spent:,}\n"
                response += f"Remaining Budget: {team_budget:,}\n\n"
                
                response += "───────────────────────────────────────\n"
                response += "👥 PLAYERS ACQUIRED\n"
                response += "───────────────────────────────────────\n"
                
                if team_players:
                    # Sort players by price (highest first)
                    team_players.sort(key=lambda x: x['price'], reverse=True)
                    
                    for i, player in enumerate(team_players, 1):
                        player_name_escaped = player['name']
                        response += f"{i}. {player_name_escaped}\n"
                        response += f"   💰 Price: {player['price']:,}\n"
                    
                    response += f"\n📊 Total Players: {len(team_players)}\n"
                    response += f"💵 Average Price: {total_spent // len(team_players) if team_players else 0:,}\n"
                else:
                    response += "No players acquired yet.\n"
                    response += "Use /next and start bidding!\n"
                
                response += "\n───────────────────────────────────────\n"
                response += "📈 TEAM STATISTICS\n"
                response += "───────────────────────────────────────\n"
                response += f"Budget Utilization: {(total_spent / FIXED_BUDGET * 100):.1f}%\n"
                response += f"Players per Budget: {len(team_players)}/{FIXED_BUDGET}\n"
                
                if team_players:
                    most_expensive = max(team_players, key=lambda x: x['price'])
                    cheapest = min(team_players, key=lambda x: x['price'])
                    response += f"Most Expensive: {most_expensive['name']} ({most_expensive['price']:,})\n"
                    response += f"Best Value: {cheapest['name']} ({cheapest['price']:,})\n"

                await event.reply(response)

            except Exception as e:
                await self.log_event(f"Error in /myteam: {str(e)}")
                await event.reply("An unexpected error occurred.")

        # Show unsold players list
        @self.client.on(events.NewMessage(pattern='/uslist'))
        async def handler(event):
            chat_id = event.chat_id

            try:
                if not self.auction_session.is_group_allowed(chat_id):
                    await event.reply("This group is not authorized.")
                    return

                current_unsold = self.auction_session.unsold_players.get(chat_id, set())

                if current_unsold:
                    unsold_list = sorted(list(current_unsold))
                    response = f"➖ **UNSOLD PLAYERS LIST (Current State)** ({len(unsold_list)} total) ➖\n\n"
                    escaped_list = [f"{i}. {await self.escape_markdown(player)}" for i, player in enumerate(unsold_list, 1)]
                    response += "\n".join(escaped_list)

                    if len(response) > 4096:
                        await event.reply("Unsold list is too long, sending in parts...")
                        for i in range(0, len(response), 4000):
                            try:
                                await event.reply(response[i:i+4000])
                            except Exception as chunk_ex:
                                await event.reply("Error sending part of the list.")
                    else:
                        await event.reply(response)
                else:
                    await event.reply("No players have been marked as unsold yet in this group.")

            except Exception as e:
                await self.log_event(f"Error in /uslist: {str(e)}")
                await event.reply("An unexpected error occurred.")

        # Filter messages in auction mode
        @self.client.on(events.NewMessage)
        async def auction_message_filter(event):
            chat_id = event.chat_id
            if not self.auction_session.auction_mode_groups.get(chat_id, False):
                return

            # Allow admin commands and countdown
            if event.text and (event.text.startswith('/') or event.text == '.'):
                return

            # Allow numeric bids from captains
            sender_username = event.sender.username
            if sender_username in ADMIN_USERNAMES:
                return

            if sender_username and self.auction_session.is_captain(chat_id, sender_username.lower()):
                try:
                    int(event.text.strip().replace(',', ''))
                    return  # Allow numeric bids from captains
                except (ValueError, TypeError):
                    pass

            # Delete other messages
            try:
                await event.delete()
            except:
                pass  # Ignore if we can't delete

    async def start(self):
        await self.client.start(bot_token=BOT_TOKEN)
        await self.setup_handlers()
        print("🤖 Vote Bot Started!")
        await self.log_event("🤖 Vote Bot Started!")
        await self.client.run_until_disconnected()

if __name__ == '__main__':
    bot = VoteBot()
    asyncio.run(bot.start())