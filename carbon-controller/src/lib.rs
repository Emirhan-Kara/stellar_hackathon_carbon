#![no_std]

use soroban_sdk::{
    contract, contractimpl, contracttype, contractevent, Address, Env, String, Symbol,
    token::{TokenClient, StellarAssetClient},
};

#[contract]
pub struct CarbonController;

#[contracttype]
#[derive(Clone)]
pub struct CarbonAssetMeta {
    pub project_id: i64,
    pub vintage_year: i32,
    pub token: Address,   // token contract id (SAC or SEP-41 token)
    pub admin: Address,   // who is allowed to mint / freeze
}

#[contracttype]
pub enum DataKey {
    Asset(Symbol),                // asset_code, e.g. "ZORLU23"
    XmlToken,                     // global XML token contract
    Listing(Symbol, Address),     // (asset_code, seller)
}

fn read_asset(e: &Env, code: Symbol) -> CarbonAssetMeta {
    let key = DataKey::Asset(code);
    e.storage()
        .instance()
        .get::<DataKey, CarbonAssetMeta>(&key)
        .unwrap_or_else(|| panic!("asset not registered"))
}

/// Carbon credit retirement event, indexed off-chain.
#[contractevent]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CarbonRetireEvent {
    #[topic]
    pub asset_code: Symbol,
    #[topic]
    pub holder: Address,
    pub amount: i128,
    pub project_id: i64,
    pub vintage_year: i32,
    pub note: String,
}

/// Simple listing: seller offers `amount` units of `asset_code` at `price` XML per unit.
/// All values are i128 with 7 decimals (same as tokens).
#[contracttype]
#[derive(Clone)]
pub struct Listing {
    pub asset_code: Symbol,
    pub seller: Address,
    pub amount: i128,
    pub price: i128, // price per 1 unit in XML (scaled by 10^7)
}

#[contractimpl]
impl CarbonController {
    /// Register an asset once you have deployed its token contract.
    /// This is typically called by the marketplace admin.
    pub fn register_asset(
        e: Env,
        asset_code: Symbol,
        project_id: i64,
        vintage_year: i32,
        token: Address,
        admin: Address,
    ) {
        // Only the provided admin can (re)register
        admin.require_auth();

        let meta = CarbonAssetMeta {
            project_id,
            vintage_year,
            token,
            admin: admin.clone(),
        };

        let key = DataKey::Asset(asset_code);
        e.storage().instance().set(&key, &meta);
    }

    /// Mint tokens to issuer when a tokenization_request is APPROVED.
    /// Only the configured admin for that asset can call this.
    pub fn mint_to_issuer(e: Env, asset_code: Symbol, issuer: Address, amount: i128) {
        let meta = read_asset(&e, asset_code);
        // Require marketplace admin signature
        meta.admin.require_auth();

        // Admin client: has `mint`
        let sac_client = StellarAssetClient::new(&e, &meta.token);
        sac_client.mint(&issuer, &amount);
    }

    /// Retire carbon credits by burning tokens from the holder.
    /// The holder must sign the transaction.
    pub fn retire(
        e: Env,
        asset_code: Symbol,
        from: Address,
        amount: i128,
        note: String,
    ) {
        // Clone because we also want to use asset_code in the event
        let meta = read_asset(&e, asset_code.clone());

        // Holder must authorize the burn
        from.require_auth();

        // Standard token interface for burn / transfer
        let token_client = TokenClient::new(&e, &meta.token);
        token_client.burn(&from, &amount);

        // Emit a carbon-specific event your indexer / backend can listen to
        CarbonRetireEvent {
            asset_code,
            holder: from,
            amount,
            project_id: meta.project_id,
            vintage_year: meta.vintage_year,
            note,
        }
        .publish(&e);
    }

    /// Simple read method to debug / inspect from frontend
    pub fn asset_info(e: Env, asset_code: Symbol) -> CarbonAssetMeta {
        read_asset(&e, asset_code)
    }

    /// Set which token contract is used as "money" (XML).
    /// You can restrict this to an admin pattern later if you want.
    pub fn set_xml_token(e: Env, caller: Address, xml_token: Address) {
        caller.require_auth();

        e.storage().instance().set(&DataKey::XmlToken, &xml_token);
    }

    /// Seller creates or updates a listing for an asset.
    ///
    /// IMPORTANT: Off-chain, seller must first call:
    ///   carbon_token.approve(controller, amount)
    /// so this contract can move `amount` tokens later.
    pub fn list_asset(e: Env, seller: Address, asset_code: Symbol, amount: i128, price: i128) {
        seller.require_auth();

        // Ensure the asset exists (panic if not)
        let _meta = read_asset(&e, asset_code.clone());

        if amount <= 0 {
            panic!("amount must be positive");
        }
        if price <= 0 {
            panic!("price must be positive");
        }

        let key = DataKey::Listing(asset_code.clone(), seller.clone());
        let listing = Listing {
            asset_code,
            seller,
            amount,
            price,
        };

        e.storage().instance().set(&key, &listing);
    }

    /// Buyer purchases `amount` units of `asset_code` from a specific seller,
    /// paying with XML token in a single atomic call.
    ///
    /// Off-chain:
    ///  - Seller must have approved controller for at least `amount` of carbon token.
    ///  - Buyer must have approved controller for at least `max_xml` of XML token.
    pub fn buy_with_xml(
        e: Env,
        buyer: Address,
        asset_code: Symbol,
        seller: Address,
        amount: i128,
        max_xml: i128,
    ) {
        buyer.require_auth();

        if amount <= 0 {
            panic!("amount must be positive");
        }

        // Read listing
        let listing_key = DataKey::Listing(asset_code.clone(), seller.clone());
        let mut listing: Listing = e
            .storage()
            .instance()
            .get(&listing_key)
            .unwrap_or_else(|| panic!("listing not found"));

        if amount > listing.amount {
            panic!("not enough listed amount");
        }

        // Read asset meta (to get carbon token contract)
        let meta = read_asset(&e, asset_code.clone());

        // Read XML token address
        let xml_token: Address = e
            .storage()
            .instance()
            .get(&DataKey::XmlToken)
            .unwrap_or_else(|| panic!("XML token not set"));

        // Compute cost_xml = amount * price
        let cost_xml = amount
            .checked_mul(listing.price)
            .expect("overflow in price calc");

        if cost_xml > max_xml {
            panic!("price exceeds max_xml");
        }

        // 1) XML: buyer -> seller
        let xml_client = TokenClient::new(&e, &xml_token);
        xml_client.transfer_from(&buyer, &buyer, &seller, &cost_xml);

        // 2) Carbon: seller -> buyer
        let carbon_client = TokenClient::new(&e, &meta.token);
        carbon_client.transfer_from(&seller, &seller, &buyer, &amount);

        // Update or remove listing
        listing.amount -= amount;
        if listing.amount > 0 {
            e.storage().instance().set(&listing_key, &listing);
        } else {
            e.storage().instance().remove(&listing_key);
        }
    }
}
