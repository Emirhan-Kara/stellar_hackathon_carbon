"""
Service for deploying Stellar smart contracts
Uses subprocess to call stellar CLI for reliability
"""
import os
import subprocess
import re
from pathlib import Path


class SorobanService:
    def __init__(self):
        # Get configuration from environment
        self.network = os.getenv("STELLAR_NETWORK", "testnet").lower()
        self.admin_secret = os.getenv("ADMIN_SECRET_KEY")
        # Support both CARBON_CONTROLLER_ADDRESS and CARBON_CONTROLLER_ID
        self.carbon_controller_address = os.getenv("CARBON_CONTROLLER_ADDRESS") or os.getenv("CARBON_CONTROLLER_ID")
        self.token_wasm_path = os.getenv("TOKEN_WASM_PATH", "../soroban-examples/token/target/wasm32v1-none/release/soroban_token_contract.wasm")
        self.rpc_url = os.getenv("STELLAR_RPC_URL")
        
        # Network passphrases for Stellar networks
        network_passphrases = {
            "testnet": "Test SDF Network ; September 2015",
            "mainnet": "Public Global Stellar Network ; September 2015",
            "futurenet": "Test SDF Future Network ; October 2022"
        }
        self.network_passphrase = os.getenv("STELLAR_NETWORK_PASSPHRASE") or network_passphrases.get(self.network)
        
        if not self.admin_secret:
            raise ValueError("ADMIN_SECRET_KEY environment variable is required")
        # Note: CARBON_CONTROLLER_ADDRESS/CARBON_CONTROLLER_ID is optional - only needed for registration
        
        # Resolve WASM path relative to backend directory
        backend_dir = Path(__file__).parent
        wasm_path = Path(self.token_wasm_path)
        if not wasm_path.is_absolute():
            wasm_path = backend_dir.parent / wasm_path
        self.token_wasm_path = str(wasm_path.resolve())
        
        if not os.path.exists(self.token_wasm_path):
            raise FileNotFoundError(f"WASM file not found: {self.token_wasm_path}")
    
    def deploy_token_contract(
        self, 
        project_identifier: str, 
        vintage_year: int,
        admin_address: str,
        decimal: int = 7
    ):
        """
        Deploy a token contract using stellar CLI.
        Returns the contract address.
        """
        try:
            # Generate symbol: project_identifier_vintage_year (using underscore for consistency)
            # Both token symbol and asset_code use underscores for Soroban Symbol compatibility
            symbol = f"{project_identifier}_{vintage_year}"
            name = f"{project_identifier} {vintage_year}"  # Name can have spaces
            
            # Build the stellar contract deploy command
            # Format: stellar contract deploy --wasm <path> --source admin --network testnet -- --admin <addr> --decimal 7 --name "NAME" --symbol "SYMBOL"
            cmd = [
                "stellar",
                "contract",
                "deploy",
                "--wasm", self.token_wasm_path,
                "--source", "admin",
                "--network", self.network,
                "--",
                "--admin", admin_address,
                "--decimal", str(decimal),
                "--name", name,
                "--symbol", symbol
            ]
            
            # Set environment variables
            env = os.environ.copy()
            env["STELLAR_SECRET_KEY"] = self.admin_secret
            
            # If using custom RPC URL, add it and network passphrase to command
            if self.rpc_url:
                # Insert --rpc-url and --network-passphrase before --network
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            # Always set network passphrase in environment (CLI may need it)
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            print(f"Deploying contract with command: {' '.join(cmd)}")
            
            # Run the command with UTF-8 encoding to handle special characters
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace problematic characters instead of failing
                env=env,
                cwd=os.path.dirname(self.token_wasm_path) or "."
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Contract deployment failed: {error_msg}")
            
            # Extract contract address from output
            # The output format is typically: "Contract ID: C..."
            output = result.stdout
            contract_id_match = re.search(r'Contract ID:\s*([A-Z0-9]+)', output)
            if contract_id_match:
                contract_address = contract_id_match.group(1)
            else:
                # Try alternative pattern
                contract_id_match = re.search(r'([A-Z0-9]{56})', output)
                if contract_id_match:
                    contract_address = contract_id_match.group(1)
                else:
                    raise Exception(f"Could not extract contract address from output: {output}")
            
            print(f"Contract deployed successfully. Address: {contract_address}")
            return contract_address
            
        except FileNotFoundError:
            raise Exception("stellar CLI not found. Please install Stellar CLI.")
        except Exception as e:
            print(f"Error deploying contract: {e}")
            raise
    
    def register_asset_in_controller(
        self, 
        asset_code: str, 
        project_id: int, 
        vintage_year: int, 
        token_address: str,
        admin_address: str
    ):
        """Register an asset in the carbon controller contract using stellar CLI"""
        if not self.carbon_controller_address:
            raise ValueError("CARBON_CONTROLLER_ADDRESS or CARBON_CONTROLLER_ID environment variable is required for asset registration")
        
        try:
            # Build the stellar contract invoke command
            cmd = [
                "stellar",
                "contract",
                "invoke",
                "--id", self.carbon_controller_address,
                "--source", "admin",
                "--network", self.network,
                "--",
                "register_asset",
                "--asset_code", asset_code,
                "--project_id", str(project_id),
                "--vintage_year", str(vintage_year),
                "--token", token_address,
                "--admin", admin_address
            ]
            
            # Set environment variables
            env = os.environ.copy()
            env["STELLAR_SECRET_KEY"] = self.admin_secret
            
            # If using custom RPC URL, add it and network passphrase to command
            if self.rpc_url:
                # Insert --rpc-url and --network-passphrase before --network
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            # Always set network passphrase in environment (CLI may need it)
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            print(f"Registering asset with command: {' '.join(cmd)}")
            
            # Run the command with UTF-8 encoding to handle special characters
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace problematic characters instead of failing
                env=env
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Asset registration failed: {error_msg}")
            
            print("Asset registered successfully in carbon controller")
            return True
            
        except FileNotFoundError:
            raise Exception("stellar CLI not found. Please install Stellar CLI.")
        except Exception as e:
            print(f"Error registering asset: {e}")
            raise
    
    def mint_to_issuer(
        self,
        asset_code: str,
        issuer_address: str,
        amount: float
    ):
        """Mint tokens to the issuer using the carbon controller contract"""
        if not self.carbon_controller_address:
            raise ValueError("CARBON_CONTROLLER_ADDRESS or CARBON_CONTROLLER_ID environment variable is required for minting")
        
        try:
            # Build the stellar contract invoke command
            # Convert amount to i128 (multiply by 10^7 for 7 decimals)
            # amount is a float (e.g., 1000.0), convert to smallest unit
            amount_i128 = int(amount * 10_000_000)  # 7 decimals
            print(f"Converting {amount} to {amount_i128} (smallest unit with 7 decimals)")
            
            cmd = [
                "stellar",
                "contract",
                "invoke",
                "--id", self.carbon_controller_address,
                "--source", "admin",
                "--network", self.network,
                "--",
                "mint_to_issuer",
                "--asset_code", asset_code,
                "--issuer", issuer_address,
                "--amount", str(amount_i128)
            ]
            
            # Set environment variables
            env = os.environ.copy()
            env["STELLAR_SECRET_KEY"] = self.admin_secret
            
            # If using custom RPC URL, add it and network passphrase to command
            if self.rpc_url:
                # Insert --rpc-url and --network-passphrase before --network
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            # Always set network passphrase in environment (CLI may need it)
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            print(f"Minting tokens with command: {' '.join(cmd)}")
            
            # Run the command with UTF-8 encoding to handle special characters
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace problematic characters instead of failing
                env=env
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Token minting failed: {error_msg}")
            
            print(f"Successfully minted {amount} tokens to {issuer_address}")
            return True
            
        except FileNotFoundError:
            raise Exception("stellar CLI not found. Please install Stellar CLI.")
        except Exception as e:
            print(f"Error minting tokens: {e}")
            raise
    
    def deploy_and_register(
        self,
        project_identifier: str,
        vintage_year: int,
        project_id: int,
        admin_address: str,
        issuer_address: str,
        quantity: float,
        decimal: int = 7
    ):
        """
        Deploy token contract, register it in carbon controller, and mint tokens to issuer.
        Returns the contract address.
        """
        # Step 1: Deploy token contract
        print(f"Step 1: Deploying token contract for {project_identifier}-{vintage_year}...")
        contract_address = self.deploy_token_contract(
            project_identifier=project_identifier,
            vintage_year=vintage_year,
            admin_address=admin_address,
            decimal=decimal
        )
        
        # Step 2: Register in carbon controller (if configured)
        # Replace hyphens with underscores for Soroban Symbol compatibility
        # Symbol type only accepts alphanumeric and underscore characters
        asset_code = f"{project_identifier}-{vintage_year}".replace("-", "_")
        if self.carbon_controller_address:
            print(f"Step 2: Registering asset in carbon controller...")
            try:
                self.register_asset_in_controller(
                    asset_code=asset_code,
                    project_id=project_id,
                    vintage_year=vintage_year,
                    token_address=contract_address,
                    admin_address=admin_address
                )
                
                # Step 3: Mint tokens to issuer
                print(f"Step 3: Minting {quantity} tokens to issuer {issuer_address}...")
                try:
                    self.mint_to_issuer(
                        asset_code=asset_code,
                        issuer_address=issuer_address,
                        amount=float(quantity)
                    )
                    print(f"✓ Successfully minted {quantity} tokens to {issuer_address}")
                except Exception as e:
                    error_msg = str(e)
                    print(f"✗ ERROR: Failed to mint tokens to issuer: {error_msg}")
                    print("Contract was deployed and registered, but minting failed.")
                    print("You may need to mint tokens manually using the carbon controller.")
                    # Re-raise the exception so the caller knows minting failed
                    raise Exception(f"Minting failed: {error_msg}")
            except Exception as e:
                print(f"Warning: Failed to register asset in carbon controller: {e}")
                print("Contract was deployed successfully, but registration failed.")
                # Continue anyway - contract is deployed
        else:
            print("Step 2: Skipping carbon controller registration (CARBON_CONTROLLER_ADDRESS/CARBON_CONTROLLER_ID not set)")
            print("Step 3: Skipping token minting (requires carbon controller)")
        
        return contract_address
    
    def get_admin_address(self):
        """Get admin public address from secret key"""
        from stellar_sdk import Keypair
        admin_keypair = Keypair.from_secret(self.admin_secret)
        return admin_keypair.public_key
    
    def approve_admin_for_token(
        self,
        token_contract_id: str,
        owner_address: str,
        amount_i128: int,
        expiration_ledger: int = None,
        owner_secret_key: str = None
    ):
        """
        Approve admin (spender) to transfer tokens on behalf of owner.
        This allows admin to use transfer_from later.
        
        Args:
            token_contract_id: The token contract address
            owner_address: The address of the token owner (seller)
            amount_i128: The amount to approve (in smallest units)
            expiration_ledger: Expiration ledger (default: very large number)
            owner_secret_key: Optional secret key for the owner. If not provided and owner != admin, will fail.
        """
        print(f"[SOROBAN] ===== APPROVE ADMIN REQUEST ======")
        print(f"[SOROBAN] Token Contract: {token_contract_id}")
        print(f"[SOROBAN] Owner: {owner_address}")
        print(f"[SOROBAN] Amount: {amount_i128} (smallest units)")
        
        admin_address = self.get_admin_address()
        print(f"[SOROBAN] Admin (spender) address: {admin_address}")
        
        # Calculate expiration ledger
        # Each ledger is ~5 seconds, so:
        # - 1 day = 17,280 ledgers
        # - 1 year = ~6,307,200 ledgers
        # Stellar network has limits on how far we can extend TTL
        # We need to get current ledger and add a reasonable amount
        if expiration_ledger is None:
            try:
                # Get current ledger using Horizon API or RPC
                current_ledger = None
                
                # Try RPC first if available
                if self.rpc_url:
                    try:
                        import requests
                        rpc_response = requests.post(
                            self.rpc_url,
                            json={
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "getLatestLedger"
                            },
                            timeout=10
                        )
                        if rpc_response.status_code == 200:
                            rpc_data = rpc_response.json()
                            if "result" in rpc_data and "sequence" in rpc_data["result"]:
                                current_ledger = int(rpc_data["result"]["sequence"])
                                print(f"[SOROBAN] Got current ledger from RPC: {current_ledger}")
                    except Exception as rpc_error:
                        print(f"[SOROBAN] RPC query failed: {rpc_error}, trying Horizon API...")
                
                # Fallback to Horizon API
                if current_ledger is None:
                    try:
                        from stellar_sdk import Server
                        horizon_url = "https://horizon-testnet.stellar.org" if self.network == "testnet" else "https://horizon.stellar.org"
                        server = Server(horizon_url=horizon_url)
                        # Get latest ledger from Horizon
                        ledgers = server.ledgers().order(desc=True).limit(1).call()
                        if ledgers and "_embedded" in ledgers and "records" in ledgers["_embedded"]:
                            if len(ledgers["_embedded"]["records"]) > 0:
                                current_ledger = int(ledgers["_embedded"]["records"][0]["sequence"])
                                print(f"[SOROBAN] Got current ledger from Horizon: {current_ledger}")
                    except Exception as horizon_error:
                        print(f"[SOROBAN] Horizon API query failed: {horizon_error}")
                
                if current_ledger is None:
                    raise Exception("Could not get current ledger from RPC or Horizon API")
                
                # Add 7 days (120,960 ledgers) to current ledger for a safe expiration
                # This is much safer and should work within network limits
                expiration_ledger = current_ledger + 120960  # 7 days
                print(f"[SOROBAN] Current ledger: {current_ledger}, Expiration: {expiration_ledger} (~7 days)")
                
            except Exception as e:
                error_msg = f"Error getting current ledger: {str(e)}"
                print(f"[SOROBAN] {error_msg}")
                raise Exception(f"{error_msg}. Cannot set expiration without current ledger.")
        
        print(f"[SOROBAN] Expiration ledger: {expiration_ledger}")
        
        try:
            # Determine which secret key to use for signing
            source_key = None
            if owner_address == admin_address:
                source_key = self.admin_secret
                print(f"[SOROBAN] Owner is admin, using admin secret key for approval")
            elif owner_secret_key:
                source_key = owner_secret_key
                print(f"[SOROBAN] Using provided owner secret key for approval")
            else:
                # This shouldn't happen if issuer is always admin, but handle it gracefully
                print(f"[SOROBAN] WARNING: Owner ({owner_address}) is not admin ({admin_address})")
                print(f"[SOROBAN] No owner secret key provided. This will likely fail.")
                print(f"[SOROBAN] Attempting to use admin key anyway (may fail if contract requires owner signature)...")
                source_key = self.admin_secret
            
            # Use secret key as source (CLI accepts secret key starting with 'S' as source)
            # This allows the CLI to sign the transaction
            cmd = [
                "stellar",
                "contract",
                "invoke",
                "--id", token_contract_id,
                "--source", source_key,  # Use secret key directly as source for signing
                "--network", self.network,
                "--",
                "approve",
                "--from", owner_address,  # This is the owner's public address (for the contract call)
                "--spender", admin_address,
                "--amount", str(amount_i128),
                "--expiration-ledger", str(expiration_ledger)
            ]
            
            env = os.environ.copy()
            # Also set in environment as backup (though --source should handle it)
            env["STELLAR_SECRET_KEY"] = source_key
            
            if self.rpc_url:
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            print(f"[SOROBAN] Executing command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            print(f"[SOROBAN] Command return code: {result.returncode}")
            print(f"[SOROBAN] Command stdout: {result.stdout}")
            if result.stderr:
                print(f"[SOROBAN] Command stderr: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                print(f"[SOROBAN] ERROR: Approval failed: {error_msg}")
                raise Exception(f"Token approval failed: {error_msg}")
            
            print(f"[SOROBAN] ✓ Admin approved successfully")
            return True
            
        except Exception as e:
            print(f"[SOROBAN] ERROR: Exception in token approval: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def check_allowance(
        self,
        token_contract_id: str,
        owner_address: str,
        spender_address: str
    ):
        """
        Check the allowance (how much spender can transfer on behalf of owner)
        """
        print(f"[SOROBAN] Checking allowance...")
        print(f"[SOROBAN] Token: {token_contract_id}")
        print(f"[SOROBAN] Owner: {owner_address}")
        print(f"[SOROBAN] Spender: {spender_address}")
        
        try:
            cmd = [
                "stellar",
                "contract",
                "invoke",
                "--id", token_contract_id,
                "--source", "admin",
                "--network", self.network,
                "--",
                "allowance",
                "--from", owner_address,
                "--spender", spender_address
            ]
            
            env = os.environ.copy()
            env["STELLAR_SECRET_KEY"] = self.admin_secret
            
            if self.rpc_url:
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                print(f"[SOROBAN] Allowance output: {output}")
                # Try to extract number from output
                try:
                    import re
                    numbers = re.findall(r'\d+', output)
                    if numbers:
                        allowance = int(numbers[-1])
                        print(f"[SOROBAN] Current allowance: {allowance} stroops")
                        return allowance
                except:
                    pass
                return None
            else:
                print(f"[SOROBAN] Allowance check failed: {result.stderr}")
                return None
        except Exception as e:
            print(f"[SOROBAN] Error checking allowance: {e}")
            return None
    
    def transfer_tokens_via_contract(
        self,
        token_contract_id: str,
        from_address: str,
        to_address: str,
        amount_i128: int
    ):
        """
        Transfer tokens using token contract's transfer_from method.
        This requires the from_address to have approved the admin (spender) first.
        """
        print(f"[SOROBAN] ===== TOKEN TRANSFER REQUEST ======")
        print(f"[SOROBAN] Token Contract: {token_contract_id}")
        print(f"[SOROBAN] From: {from_address}")
        print(f"[SOROBAN] To: {to_address}")
        print(f"[SOROBAN] Amount: {amount_i128} (smallest units)")
        
        admin_address = self.get_admin_address()
        print(f"[SOROBAN] Admin address (spender): {admin_address}")
        
        # Check allowance first
        print(f"[SOROBAN] Checking current allowance...")
        current_allowance = self.check_allowance(
            token_contract_id=token_contract_id,
            owner_address=from_address,
            spender_address=admin_address
        )
        
        if current_allowance is not None:
            if current_allowance < amount_i128:
                print(f"[SOROBAN] ERROR: Insufficient allowance!")
                print(f"[SOROBAN] Current: {current_allowance} stroops, Needed: {amount_i128} stroops")
                raise Exception(
                    f"Insufficient allowance. Current: {current_allowance} stroops, "
                    f"Needed: {amount_i128} stroops. Admin must be approved for more tokens."
                )
            else:
                print(f"[SOROBAN] ✓ Allowance sufficient: {current_allowance} >= {amount_i128}")
        else:
            print(f"[SOROBAN] Could not check allowance, proceeding anyway...")
        
        # Try transfer_from (requires approval)
        try:
            print(f"[SOROBAN] Attempting transfer_from...")
            cmd = [
                "stellar",
                "contract",
                "invoke",
                "--id", token_contract_id,
                "--source", "admin",
                "--network", self.network,
                "--",
                "transfer_from",
                "--spender", admin_address,
                "--from", from_address,
                "--to", to_address,
                "--amount", str(amount_i128)
            ]
            
            env = os.environ.copy()
            env["STELLAR_SECRET_KEY"] = self.admin_secret
            
            if self.rpc_url:
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            print(f"[SOROBAN] Executing command: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            print(f"[SOROBAN] Command return code: {result.returncode}")
            print(f"[SOROBAN] Command stdout: {result.stdout}")
            if result.stderr:
                print(f"[SOROBAN] Command stderr: {result.stderr}")
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                print(f"[SOROBAN] transfer_from failed: {error_msg}")
                print(f"[SOROBAN] This likely means seller hasn't approved admin. Trying alternative approach...")
                
                # Alternative: Use transfer method which requires seller to sign
                # For now, we'll raise an error with clear message
                raise Exception(
                    f"Token transfer requires seller approval. "
                    f"Seller ({from_address}) must approve admin ({admin_address}) first. "
                    f"Error: {error_msg}"
                )
            
            print(f"[SOROBAN] ✓ Token transfer successful via transfer_from")
            return True
            
        except Exception as e:
            print(f"[SOROBAN] ERROR: Exception in token transfer: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def get_token_balance(
        self,
        token_contract_id: str,
        address: str
    ):
        """
        Get token balance for an address.
        Returns balance in smallest units (stroops).
        """
        try:
            cmd = [
                "stellar",
                "contract",
                "invoke",
                "--id", token_contract_id,
                "--source", "admin",
                "--network", self.network,
                "--",
                "balance",
                "--id", address
            ]
            
            env = os.environ.copy()
            env["STELLAR_SECRET_KEY"] = self.admin_secret
            
            if self.rpc_url:
                network_idx = cmd.index("--network")
                cmd.insert(network_idx, "--rpc-url")
                cmd.insert(network_idx + 1, self.rpc_url)
                cmd.insert(network_idx + 2, "--network-passphrase")
                cmd.insert(network_idx + 3, self.network_passphrase)
            
            if self.network_passphrase:
                env["STELLAR_NETWORK_PASSPHRASE"] = self.network_passphrase
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                try:
                    import re
                    numbers = re.findall(r'\d+', output)
                    if numbers:
                        balance = int(numbers[-1])
                        return balance
                except:
                    pass
            return None
        except Exception as e:
            print(f"[SOROBAN] Error getting token balance: {e}")
            return None
    
    def submit_signed_transaction(self, signed_xdr: str):
        """
        Submit a signed Soroban transaction XDR.
        Uses RPC if available, falls back to Horizon.
        """
        try:
            import requests
            
            # Try RPC first (preferred for Soroban transactions)
            if self.rpc_url:
                try:
                    print(f"[SOROBAN] Submitting signed transaction via RPC...")
                    rpc_response = requests.post(
                        self.rpc_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "sendTransaction",
                            "params": {
                                "transaction": signed_xdr
                            }
                        },
                        timeout=30
                    )
                    if rpc_response.status_code == 200:
                        rpc_data = rpc_response.json()
                        if "result" in rpc_data and "transactionHash" in rpc_data["result"]:
                            tx_hash = rpc_data["result"]["transactionHash"]
                            print(f"[SOROBAN] ✓ Transaction submitted via RPC: {tx_hash}")
                            return tx_hash
                        elif "error" in rpc_data:
                            error_info = rpc_data["error"]
                            print(f"[SOROBAN] RPC submission failed: {error_info}")
                            # Continue to Horizon fallback
                        else:
                            print(f"[SOROBAN] Unexpected RPC response: {rpc_data}")
                            # Continue to Horizon fallback
                except Exception as rpc_error:
                    print(f"[SOROBAN] RPC submission error: {rpc_error}")
                    # Continue to Horizon fallback
            
            # Fallback to Horizon
            print(f"[SOROBAN] Trying Horizon submission...")
            horizon_url = "https://horizon-testnet.stellar.org" if self.network == "testnet" else "https://horizon.stellar.org"
            response = requests.post(
                f'{horizon_url}/transactions',
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=f'tx={requests.utils.quote(signed_xdr)}',
                timeout=30
            )
            
            if response.ok:
                result = response.json()
                transaction_hash = result.get('hash')
                if transaction_hash:
                    print(f"[SOROBAN] ✓ Transaction submitted via Horizon: {transaction_hash}")
                    return transaction_hash
                else:
                    raise Exception(f"Horizon submission succeeded but no hash in response: {result}")
            else:
                error_text = response.text
                print(f"[SOROBAN] Horizon submission failed: {error_text}")
                raise Exception(f"Transaction submission failed: {error_text}")
                
        except Exception as e:
            print(f"[SOROBAN] Error submitting transaction: {e}")
            import traceback
            traceback.print_exc()
            raise

