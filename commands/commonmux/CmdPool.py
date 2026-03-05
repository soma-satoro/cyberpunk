from evennia.commands.default.muxcommand import MuxCommand

class CmdPool(MuxCommand):
    """
    View and manage character pools (administrative functions).
    
    Usage:
        +pool - Show all available pools
        +pool <pool> - Show specific pool status
        +pool/<pool> - Show specific pool status 
        +pool/<pool>/set <current>/<max> - Set pool values (staff only)
        +pool/<pool>/reset - Reset pool to maximum (staff only)
        
    Available Pools:
        willpower - Universal pool for all characters
        essence - Werewolf spiritual energy (based on Primal Urge)
        blood - Vampire blood pool (based on Blood Potency)
        glamour - Changeling glamour (based on Wyrd)
        mana - Mage quintessence (based on Gnosis)
        plasm - Geist ectoplasm (based on Synergy)
        satiety - Beast hunger satisfaction
        instability - Deviant reality distortion (based on Deviation)
        aether - Demon occult matrix fuel (based on Primum)
        pyros - Promethean divine fire (based on Azoth)
        
    Pool Maximums (Power Stat 1-10):
        1-4: 10, 11, 12, 13 points
        5: 15 points
        6-8: 20, 25, 30 points  
        9-10: 50, 75 points
        Special: Blood Potency 0 = Stamina value
        
    Note: Use +spend and +gain commands to spend/gain pool points.
        
    Examples:
        +pool/essence - Check essence pool
        +pool/mana/set 5/10 - Set mana to 5/10 (staff)
        +pool/willpower/reset - Reset willpower to max (staff)
    """
    
    key = "+pool"
    aliases = ["pool", "pools"]
    help_category = "Roleplaying Tools"
    
    def _get_template_info(self, caller):
        """Get character template and related pool information"""
        other = caller.db.stats.get("other", {})
        advantages = caller.db.stats.get("advantages", {})
        template = other.get("template", "Mortal").lower()
        
        # Define pool configurations for each template
        template_pools = {
            "changeling": [
                {
                    "name": "glamour",
                    "display": "Glamour",
                    "max_stat": "wyrd",
                    "current_attr": "glamour_current"
                }
            ],
            "werewolf": [
                {
                    "name": "essence",
                    "display": "Essence",
                    "max_stat": "primal_urge",
                    "current_attr": "essence_current"
                }
            ],
            "vampire": [
                {
                    "name": "blood",
                    "display": "Blood",
                    "max_stat": "blood_potency",
                    "current_attr": "blood_current"
                }
            ],
            "mage": [
                {
                    "name": "mana",
                    "display": "Mana", 
                    "max_stat": "gnosis",
                    "current_attr": "mana_current"
                }
            ],
            "geist": [
                {
                    "name": "plasm",
                    "display": "Plasm",
                    "max_stat": "synergy", 
                    "current_attr": "plasm_current"
                }
            ],
            "beast": [
                {
                    "name": "satiety",
                    "display": "Satiety",
                    "max_stat": "satiety",  # Satiety is both the stat and the pool
                    "current_attr": "satiety_current"
                }
            ],
            "deviant": [
                {
                    "name": "instability",
                    "display": "Instability",
                    "max_stat": "deviation",
                    "current_attr": "instability_current"
                }
            ],
            "demon": [
                {
                    "name": "aether",
                    "display": "Aether",
                    "max_stat": "primum",
                    "current_attr": "aether_current"
                }
            ],
            "promethean": [
                {
                    "name": "pyros",
                    "display": "Pyros",
                    "max_stat": "azoth",
                    "current_attr": "pyros_current"
                }
            ]
        }
        
        return template, template_pools.get(template, []), advantages
    
    def _calculate_supernatural_pool_max(self, power_stat_value, pool_name=""):
        """Calculate supernatural pool maximum from power stat using proper lookup tables"""
        # Special case for Blood Potency 0 (uses Stamina)
        if pool_name == "blood" and power_stat_value == 0:
            return None  # Will need to get stamina value separately
        
        # Standard supernatural pool lookup table
        pool_lookup = {
            1: 10,
            2: 11, 
            3: 12,
            4: 13,
            5: 15,
            6: 20,
            7: 25,
            8: 30,
            9: 50,
            10: 75
        }
        
        return pool_lookup.get(power_stat_value, 10)  # Default to 10 if invalid
    
    def _get_pool_info(self, caller, pool_name):
        """Get current and maximum values for a specific pool"""
        if pool_name == "willpower":
            advantages = caller.db.stats.get("advantages", {})
            willpower_max = advantages.get("willpower")
            if willpower_max is None:
                # Calculate from resolve + composure
                attrs = caller.db.stats.get("attributes", {})
                resolve = attrs.get("resolve", 1)
                composure = attrs.get("composure", 1)
                willpower_max = resolve + composure
            willpower_current = caller.db.willpower_current
            if willpower_current is None:
                willpower_current = willpower_max
                caller.db.willpower_current = willpower_current
            return willpower_current, willpower_max, "willpower_current"
        
        # Check template-specific pools
        template, available_pools, advantages = self._get_template_info(caller)
        
        for pool in available_pools:
            if pool["name"] == pool_name:
                max_stat_value = advantages.get(pool["max_stat"], 0)
                if max_stat_value == 0:
                    return None, None, None  # Character doesn't have this power stat
                
                # Special handling for vampire blood pool with Blood Potency 0
                if pool_name == "blood" and max_stat_value == 0:
                    # Use stamina value for Blood Potency 0
                    attributes = caller.db.stats.get("attributes", {})
                    stamina = attributes.get("stamina", 1)
                    pool_max = stamina
                else:
                    # Use lookup table for supernatural pools
                    pool_max = self._calculate_supernatural_pool_max(max_stat_value, pool_name)
                
                pool_current = getattr(caller.db, pool["current_attr"], None)
                if pool_current is None:
                    pool_current = pool_max
                    setattr(caller.db, pool["current_attr"], pool_current)
                
                return pool_current, pool_max, pool["current_attr"]
        
        return None, None, None
    
    def _show_all_pools(self, caller):
        """Display all available pools for the character"""
        output = ["|wAvailable Pools:|n"]
        
        # Always show willpower
        willpower_current, willpower_max, _ = self._get_pool_info(caller, "willpower")
        output.append(f"  Willpower: {willpower_current}/{willpower_max}")
        
        # Show template-specific pools
        template, available_pools, advantages = self._get_template_info(caller)
        
        for pool in available_pools:
            current, maximum, _ = self._get_pool_info(caller, pool["name"])
            if current is not None and maximum is not None:
                output.append(f"  {pool['display']}: {current}/{maximum}")
        
        if len(output) == 1:
            output.append("  No supernatural pools available.")
        
        caller.msg("\n".join(output))
    
    def _validate_pool(self, caller, pool_name):
        """Check if the pool name is valid for this character"""
        if pool_name == "willpower":
            return True
        
        template, available_pools, _ = self._get_template_info(caller)
        return any(pool["name"] == pool_name for pool in available_pools)
    
    def func(self):
        """Manage character pools"""
        
        # No arguments - show all pools
        if not self.args and not self.switches:
            self._show_all_pools(self.caller)
            return
        
        # Determine which pool we're working with
        pool_name = None
        
        # Check if pool is specified in switches
        for switch in self.switches:
            if switch in ["willpower", "essence", "blood", "glamour", "mana", "plasm", "satiety", "instability", "aether", "pyros"]:
                pool_name = switch
                break
        
        # If no pool in switches, check args
        if not pool_name and self.args:
            potential_pool = self.args.split()[0].lower()
            if potential_pool in ["willpower", "essence", "blood", "glamour", "mana", "plasm", "satiety", "instability", "aether", "pyros"]:
                pool_name = potential_pool
        
        # If still no pool specified, show error
        if not pool_name:
            self.caller.msg("Usage: +pool/<pool_name>/action or +pool <pool_name>")
            self.caller.msg("Available pools: willpower, essence, blood, glamour, mana, plasm, satiety, instability, aether, pyros")
            return
        
        # Validate pool for this character
        if not self._validate_pool(self.caller, pool_name):
            self.caller.msg(f"You don't have access to the {pool_name} pool.")
            self._show_all_pools(self.caller)
            return
        
        # Get pool information
        current, maximum, current_attr = self._get_pool_info(self.caller, pool_name)
        if current is None:
            self.caller.msg(f"You don't have the {pool_name} pool available.")
            return
        
        # Just showing the pool status
        if not any(action in self.switches for action in ["set", "reset"]):
            self.caller.msg(f"{pool_name.title()}: {current}/{maximum}")
            return
        
        # Handle pool actions
        if "set" in self.switches:
            # Staff only
            if not self.caller.check_permstring("Builder"):
                self.caller.msg(f"You don't have permission to set {pool_name}.")
                return
            
            if not self.args or "/" not in self.args:
                self.caller.msg(f"Usage: +pool/{pool_name}/set <current>/<max>")
                return
            
            try:
                args_part = self.args.split()[-1]  # Get the last argument in case pool name was also specified
                current_str, max_str = args_part.split("/", 1)
                new_current = int(current_str)
                new_max = int(max_str)
                
                if new_current < 0 or new_max < 1:
                    self.caller.msg(f"{pool_name.title()} values must be positive.")
                    return
                
                if new_current > new_max:
                    self.caller.msg(f"Current {pool_name} cannot exceed maximum.")
                    return
                
                # Set the values
                if pool_name == "willpower":
                    if not self.caller.db.stats:
                        self.caller.db.stats = {}
                    if "advantages" not in self.caller.db.stats:
                        self.caller.db.stats["advantages"] = {}
                    self.caller.db.stats["advantages"]["willpower"] = new_max
                    self.caller.db.willpower_current = new_current
                else:
                    setattr(self.caller.db, current_attr, new_current)
                    # Note: Setting max for supernatural pools would require changing the power stat
                
                self.caller.msg(f"{pool_name.title()} set to {new_current}/{new_max}")
                
            except ValueError:
                self.caller.msg(f"Usage: +pool/{pool_name}/set <current>/<max> (numbers only)")
        
        elif "reset" in self.switches:
            # Staff only
            if not self.caller.check_permstring("Builder"):
                self.caller.msg(f"You don't have permission to reset {pool_name}.")
                return
            
            if pool_name == "willpower":
                self.caller.db.willpower_current = maximum
            else:
                setattr(self.caller.db, current_attr, maximum)
            
            self.caller.msg(f"{pool_name.title()} reset to maximum: {maximum}/{maximum}")
        
        else:
            self.caller.msg("Valid actions: /set, /reset") 

from evennia.commands.default.muxcommand import MuxCommand

class CmdGain(MuxCommand):
    """
    Regain points in character pools (willpower and supernatural pools).
    
    Usage:
        +gain <pool>=<amount> - Gain amount in specified pool
        +gain <pool> - Gain 1 point in specified pool
        +gain - Show available pools
        
    Available Pools:
        willpower - Universal pool for all characters
        essence - Werewolf spiritual energy (based on Primal Urge)
        blood - Vampire blood pool (based on Blood Potency)
        glamour - Changeling glamour (based on Wyrd)
        mana - Mage quintessence (based on Gnosis)
        plasm - Geist ectoplasm (based on Synergy)
        satiety - Beast hunger satisfaction
        instability - Deviant reality distortion (based on Deviation)
        aether - Demon occult matrix fuel (based on Primum)
        pyros - Promethean divine fire (based on Azoth)
        
    Examples:
        +gain willpower=2 - Gain 2 willpower
        +gain essence - Gain 1 essence
        +gain plasm=3 - Gain 3 plasm
    """
    
    key = "+gain"
    aliases = ["gain"]
    help_category = "Roleplaying Tools"
    
    def _get_template_info(self, caller):
        """Get character template and related pool information"""
        other = caller.db.stats.get("other", {})
        advantages = caller.db.stats.get("advantages", {})
        template = other.get("template", "Mortal").lower()
        
        # Define pool configurations for each template
        template_pools = {
            "changeling": [
                {
                    "name": "glamour",
                    "display": "Glamour",
                    "max_stat": "wyrd",
                    "current_attr": "glamour_current"
                }
            ],
            "werewolf": [
                {
                    "name": "essence",
                    "display": "Essence",
                    "max_stat": "primal_urge",
                    "current_attr": "essence_current"
                }
            ],
            "vampire": [
                {
                    "name": "blood",
                    "display": "Blood",
                    "max_stat": "blood_potency",
                    "current_attr": "blood_current"
                }
            ],
            "mage": [
                {
                    "name": "mana",
                    "display": "Mana", 
                    "max_stat": "gnosis",
                    "current_attr": "mana_current"
                }
            ],
            "geist": [
                {
                    "name": "plasm",
                    "display": "Plasm",
                    "max_stat": "synergy", 
                    "current_attr": "plasm_current"
                }
            ],
            "beast": [
                {
                    "name": "satiety",
                    "display": "Satiety",
                    "max_stat": "satiety",  # Satiety is both the stat and the pool
                    "current_attr": "satiety_current"
                }
            ],
            "deviant": [
                {
                    "name": "instability",
                    "display": "Instability",
                    "max_stat": "deviation",
                    "current_attr": "instability_current"
                }
            ],
            "demon": [
                {
                    "name": "aether",
                    "display": "Aether",
                    "max_stat": "primum",
                    "current_attr": "aether_current"
                }
            ],
            "promethean": [
                {
                    "name": "pyros",
                    "display": "Pyros",
                    "max_stat": "azoth",
                    "current_attr": "pyros_current"
                }
            ]
        }
        
        return template, template_pools.get(template, []), advantages
    
    def _calculate_supernatural_pool_max(self, power_stat_value, pool_name=""):
        """Calculate supernatural pool maximum from power stat using proper lookup tables"""
        # Special case for Blood Potency 0 (uses Stamina)
        if pool_name == "blood" and power_stat_value == 0:
            return None  # Will need to get stamina value separately
        
        # Standard supernatural pool lookup table
        pool_lookup = {
            1: 10,
            2: 11, 
            3: 12,
            4: 13,
            5: 15,
            6: 20,
            7: 25,
            8: 30,
            9: 50,
            10: 75
        }
        
        return pool_lookup.get(power_stat_value, 10)  # Default to 10 if invalid
    
    def _get_pool_info(self, caller, pool_name):
        """Get current and maximum values for a specific pool"""
        if pool_name == "willpower":
            advantages = caller.db.stats.get("advantages", {})
            willpower_max = advantages.get("willpower")
            if willpower_max is None:
                # Calculate from resolve + composure
                attrs = caller.db.stats.get("attributes", {})
                resolve = attrs.get("resolve", 1)
                composure = attrs.get("composure", 1)
                willpower_max = resolve + composure
            willpower_current = caller.db.willpower_current
            if willpower_current is None:
                willpower_current = willpower_max
                caller.db.willpower_current = willpower_current
            return willpower_current, willpower_max, "willpower_current"
        
        # Check template-specific pools
        template, available_pools, advantages = self._get_template_info(caller)
        
        for pool in available_pools:
            if pool["name"] == pool_name:
                max_stat_value = advantages.get(pool["max_stat"], 0)
                if max_stat_value == 0:
                    return None, None, None  # Character doesn't have this power stat
                
                # Special handling for vampire blood pool with Blood Potency 0
                if pool_name == "blood" and max_stat_value == 0:
                    # Use stamina value for Blood Potency 0
                    attributes = caller.db.stats.get("attributes", {})
                    stamina = attributes.get("stamina", 1)
                    pool_max = stamina
                else:
                    # Use lookup table for supernatural pools
                    pool_max = self._calculate_supernatural_pool_max(max_stat_value, pool_name)
                
                pool_current = getattr(caller.db, pool["current_attr"], None)
                if pool_current is None:
                    pool_current = pool_max
                    setattr(caller.db, pool["current_attr"], pool_current)
                
                return pool_current, pool_max, pool["current_attr"]
        
        return None, None, None
    
    def _show_all_pools(self, caller):
        """Display all available pools for the character"""
        output = ["|wAvailable Pools:|n"]
        
        # Always show willpower
        willpower_current, willpower_max, _ = self._get_pool_info(caller, "willpower")
        output.append(f"  Willpower: {willpower_current}/{willpower_max}")
        
        # Show template-specific pools
        template, available_pools, advantages = self._get_template_info(caller)
        
        for pool in available_pools:
            current, maximum, _ = self._get_pool_info(caller, pool["name"])
            if current is not None and maximum is not None:
                output.append(f"  {pool['display']}: {current}/{maximum}")
        
        if len(output) == 1:
            output.append("  No supernatural pools available.")
        
        caller.msg("\n".join(output))
    
    def _validate_pool(self, caller, pool_name):
        """Check if the pool name is valid for this character"""
        if pool_name == "willpower":
            return True
        
        template, available_pools, _ = self._get_template_info(caller)
        return any(pool["name"] == pool_name for pool in available_pools)
    
    def func(self):
        """Gain points in character pools"""
        
        # No arguments - show available pools
        if not self.args:
            self._show_all_pools(self.caller)
            return
        
        # Parse arguments - looking for pool=amount or just pool
        pool_name = None
        amount = 1
        
        if "=" in self.args:
            pool_name, amount_str = self.args.split("=", 1)
            pool_name = pool_name.strip().lower()
            try:
                amount = int(amount_str.strip())
            except ValueError:
                self.caller.msg("Amount must be a number.")
                return
        else:
            pool_name = self.args.strip().lower()
        
        # Validate pool name
        valid_pools = ["willpower", "essence", "blood", "glamour", "mana", "plasm", "satiety", "instability", "aether", "pyros"]
        if pool_name not in valid_pools:
            self.caller.msg(f"Unknown pool: {pool_name}")
            self.caller.msg(f"Valid pools: {', '.join(valid_pools)}")
            return
        
        # Validate pool for this character
        if not self._validate_pool(self.caller, pool_name):
            self.caller.msg(f"You don't have access to the {pool_name} pool.")
            self._show_all_pools(self.caller)
            return
        
        # Get pool information
        current, maximum, current_attr = self._get_pool_info(self.caller, pool_name)
        if current is None:
            self.caller.msg(f"You don't have the {pool_name} pool available.")
            return
        
        # Validate amount
        if amount < 1:
            self.caller.msg(f"You must gain at least 1 {pool_name}.")
            return
        
        # Calculate new current value (can't exceed maximum)
        new_current = min(maximum, current + amount)
        gained = new_current - current
        
        if gained == 0:
            self.caller.msg(f"Your {pool_name} is already at maximum.")
            return
        
        # Gain the pool points
        if pool_name == "willpower":
            self.caller.db.willpower_current = new_current
        else:
            setattr(self.caller.db, current_attr, new_current)
        
        self.caller.msg(f"You gain {gained} {pool_name}. Current: {new_current}/{maximum}")


from evennia.commands.default.muxcommand import MuxCommand

class CmdSpend(MuxCommand):
    """
    Spend points from character pools (willpower and supernatural pools).
    
    Usage:
        +spend <pool>=<amount> - Spend amount from specified pool
        +spend <pool> - Spend 1 point from specified pool
        +spend - Show available pools
        
    Available Pools:
        willpower - Universal pool for all characters
        essence - Werewolf spiritual energy (based on Primal Urge)
        blood - Vampire blood pool (based on Blood Potency)
        glamour - Changeling glamour (based on Wyrd)
        mana - Mage quintessence (based on Gnosis)
        plasm - Geist ectoplasm (based on Synergy)
        satiety - Beast hunger satisfaction
        instability - Deviant reality distortion (based on Deviation)
        aether - Demon occult matrix fuel (based on Primum)
        pyros - Promethean divine fire (based on Azoth)
        
    Examples:
        +spend willpower=2 - Spend 2 willpower
        +spend essence - Spend 1 essence
        +spend plasm=3 - Spend 3 plasm
    """
    
    key = "+spend"
    aliases = ["spend"]
    help_category = "Roleplaying Tools"
    
    def _get_template_info(self, caller):
        """Get character template and related pool information"""
        other = caller.db.stats.get("other", {})
        advantages = caller.db.stats.get("advantages", {})
        template = other.get("template", "Mortal").lower()
        
        # Define pool configurations for each template
        template_pools = {
            "changeling": [
                {
                    "name": "glamour",
                    "display": "Glamour",
                    "max_stat": "wyrd",
                    "current_attr": "glamour_current"
                }
            ],
            "werewolf": [
                {
                    "name": "essence",
                    "display": "Essence",
                    "max_stat": "primal_urge",
                    "current_attr": "essence_current"
                }
            ],
            "vampire": [
                {
                    "name": "blood",
                    "display": "Blood",
                    "max_stat": "blood_potency",
                    "current_attr": "blood_current"
                }
            ],
            "mage": [
                {
                    "name": "mana",
                    "display": "Mana", 
                    "max_stat": "gnosis",
                    "current_attr": "mana_current"
                }
            ],
            "geist": [
                {
                    "name": "plasm",
                    "display": "Plasm",
                    "max_stat": "synergy", 
                    "current_attr": "plasm_current"
                }
            ],
            "beast": [
                {
                    "name": "satiety",
                    "display": "Satiety",
                    "max_stat": "satiety",  # Satiety is both the stat and the pool
                    "current_attr": "satiety_current"
                }
            ],
            "deviant": [
                {
                    "name": "instability",
                    "display": "Instability",
                    "max_stat": "deviation",
                    "current_attr": "instability_current"
                }
            ],
            "demon": [
                {
                    "name": "aether",
                    "display": "Aether",
                    "max_stat": "primum",
                    "current_attr": "aether_current"
                }
            ],
            "promethean": [
                {
                    "name": "pyros",
                    "display": "Pyros",
                    "max_stat": "azoth",
                    "current_attr": "pyros_current"
                }
            ]
        }
        
        return template, template_pools.get(template, []), advantages
    
    def _calculate_supernatural_pool_max(self, power_stat_value, pool_name=""):
        """Calculate supernatural pool maximum from power stat using proper lookup tables"""
        # Special case for Blood Potency 0 (uses Stamina)
        if pool_name == "blood" and power_stat_value == 0:
            return None  # Will need to get stamina value separately
        
        # Standard supernatural pool lookup table
        pool_lookup = {
            1: 10,
            2: 11, 
            3: 12,
            4: 13,
            5: 15,
            6: 20,
            7: 25,
            8: 30,
            9: 50,
            10: 75
        }
        
        return pool_lookup.get(power_stat_value, 10)  # Default to 10 if invalid
    
    def _get_pool_info(self, caller, pool_name):
        """Get current and maximum values for a specific pool"""
        if pool_name == "willpower":
            advantages = caller.db.stats.get("advantages", {})
            willpower_max = advantages.get("willpower")
            if willpower_max is None:
                # Calculate from resolve + composure
                attrs = caller.db.stats.get("attributes", {})
                resolve = attrs.get("resolve", 1)
                composure = attrs.get("composure", 1)
                willpower_max = resolve + composure
            willpower_current = caller.db.willpower_current
            if willpower_current is None:
                willpower_current = willpower_max
                caller.db.willpower_current = willpower_current
            return willpower_current, willpower_max, "willpower_current"
        
        # Check template-specific pools
        template, available_pools, advantages = self._get_template_info(caller)
        
        for pool in available_pools:
            if pool["name"] == pool_name:
                max_stat_value = advantages.get(pool["max_stat"], 0)
                if max_stat_value == 0:
                    return None, None, None  # Character doesn't have this power stat
                
                # Special handling for vampire blood pool with Blood Potency 0
                if pool_name == "blood" and max_stat_value == 0:
                    # Use stamina value for Blood Potency 0
                    attributes = caller.db.stats.get("attributes", {})
                    stamina = attributes.get("stamina", 1)
                    pool_max = stamina
                else:
                    # Use lookup table for supernatural pools
                    pool_max = self._calculate_supernatural_pool_max(max_stat_value, pool_name)
                
                pool_current = getattr(caller.db, pool["current_attr"], None)
                if pool_current is None:
                    pool_current = pool_max
                    setattr(caller.db, pool["current_attr"], pool_current)
                
                return pool_current, pool_max, pool["current_attr"]
        
        return None, None, None
    
    def _show_all_pools(self, caller):
        """Display all available pools for the character"""
        output = ["|wAvailable Pools:|n"]
        
        # Always show willpower
        willpower_current, willpower_max, _ = self._get_pool_info(caller, "willpower")
        output.append(f"  Willpower: {willpower_current}/{willpower_max}")
        
        # Show template-specific pools
        template, available_pools, advantages = self._get_template_info(caller)
        
        for pool in available_pools:
            current, maximum, _ = self._get_pool_info(caller, pool["name"])
            if current is not None and maximum is not None:
                output.append(f"  {pool['display']}: {current}/{maximum}")
        
        if len(output) == 1:
            output.append("  No supernatural pools available.")
        
        caller.msg("\n".join(output))
    
    def _validate_pool(self, caller, pool_name):
        """Check if the pool name is valid for this character"""
        if pool_name == "willpower":
            return True
        
        template, available_pools, _ = self._get_template_info(caller)
        return any(pool["name"] == pool_name for pool in available_pools)
    
    def func(self):
        """Spend points from character pools"""
        
        # No arguments - show available pools
        if not self.args:
            self._show_all_pools(self.caller)
            return
        
        # Parse arguments - looking for pool=amount or just pool
        pool_name = None
        amount = 1
        
        if "=" in self.args:
            pool_name, amount_str = self.args.split("=", 1)
            pool_name = pool_name.strip().lower()
            try:
                amount = int(amount_str.strip())
            except ValueError:
                self.caller.msg("Amount must be a number.")
                return
        else:
            pool_name = self.args.strip().lower()
        
        # Validate pool name
        valid_pools = ["willpower", "essence", "blood", "glamour", "mana", "plasm", "satiety", "instability", "aether", "pyros"]
        if pool_name not in valid_pools:
            self.caller.msg(f"Unknown pool: {pool_name}")
            self.caller.msg(f"Valid pools: {', '.join(valid_pools)}")
            return
        
        # Validate pool for this character
        if not self._validate_pool(self.caller, pool_name):
            self.caller.msg(f"You don't have access to the {pool_name} pool.")
            self._show_all_pools(self.caller)
            return
        
        # Get pool information
        current, maximum, current_attr = self._get_pool_info(self.caller, pool_name)
        if current is None:
            self.caller.msg(f"You don't have the {pool_name} pool available.")
            return
        
        # Validate amount
        if amount < 1:
            self.caller.msg(f"You must spend at least 1 {pool_name}.")
            return
        
        if current < amount:
            self.caller.msg(f"You only have {current} {pool_name} remaining.")
            return
        
        # Spend the pool points
        new_current = current - amount
        if pool_name == "willpower":
            self.caller.db.willpower_current = new_current
        else:
            setattr(self.caller.db, current_attr, new_current)
        
        self.caller.msg(f"You spend {amount} {pool_name}. Current: {new_current}/{maximum}")
        
        # Notify room if spending supernatural energy
        if pool_name != "willpower" and amount > 1:
            self.caller.location.msg_contents(
                f"{self.caller.name} channels supernatural energy.",
                exclude=self.caller
            )
