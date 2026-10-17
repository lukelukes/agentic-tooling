import { DatabaseSync } from 'node:sqlite';

// The service's own database. Production passes a file path; ':memory:' is a
// real SQLite engine too.

export interface Product {
  sku: string;
  priceCents: number;
  stock: number;
}

export interface Coupon {
  code: string;
  percentOff: number;
  minSubtotalCents: number;
  validUntil: string; // ISO-8601 instant, inclusive
  maxRedemptions: number;
}

export interface StoredOrder {
  id: string;
  customerId: string;
  email: string;
  totalCents: number;
  couponCode: string | null;
  createdAt: string;
}

export class CheckoutStore {
  private constructor(private readonly db: DatabaseSync) {}

  static open(path: string): CheckoutStore {
    const db = new DatabaseSync(path);
    db.exec(`
      CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY, price_cents INTEGER NOT NULL, stock INTEGER NOT NULL CHECK (stock >= 0));
      CREATE TABLE IF NOT EXISTS coupons (
        code TEXT PRIMARY KEY, percent_off INTEGER NOT NULL, min_subtotal_cents INTEGER NOT NULL,
        valid_until TEXT NOT NULL, max_redemptions INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS redemptions (
        code TEXT NOT NULL, customer_id TEXT NOT NULL, PRIMARY KEY (code, customer_id));
      CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, email TEXT NOT NULL,
        total_cents INTEGER NOT NULL, coupon_code TEXT, created_at TEXT NOT NULL);
    `);
    return new CheckoutStore(db);
  }

  addProduct(p: Product): void {
    this.db.prepare('INSERT INTO products VALUES (?, ?, ?)').run(p.sku, p.priceCents, p.stock);
  }

  addCoupon(c: Coupon): void {
    this.db
      .prepare('INSERT INTO coupons VALUES (?, ?, ?, ?, ?)')
      .run(c.code, c.percentOff, c.minSubtotalCents, c.validUntil, c.maxRedemptions);
  }

  getProduct(sku: string): Product | undefined {
    const row = this.db.prepare('SELECT sku, price_cents, stock FROM products WHERE sku = ?').get(sku) as
      | { sku: string; price_cents: number; stock: number }
      | undefined;
    return row && { sku: row.sku, priceCents: row.price_cents, stock: row.stock };
  }

  findCoupon(code: string): Coupon | undefined {
    const row = this.db.prepare('SELECT * FROM coupons WHERE code = ?').get(code) as
      | { code: string; percent_off: number; min_subtotal_cents: number; valid_until: string; max_redemptions: number }
      | undefined;
    return (
      row && {
        code: row.code,
        percentOff: row.percent_off,
        minSubtotalCents: row.min_subtotal_cents,
        validUntil: row.valid_until,
        maxRedemptions: row.max_redemptions,
      }
    );
  }

  /** Decrements stock if enough is available. Returns false otherwise. */
  reserveStock(sku: string, quantity: number): boolean {
    const r = this.db
      .prepare('UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?')
      .run(quantity, sku, quantity);
    return r.changes === 1;
  }

  redemptionCount(code: string): number {
    const row = this.db.prepare('SELECT COUNT(*) AS n FROM redemptions WHERE code = ?').get(code) as { n: number };
    return row.n;
  }

  hasRedeemed(code: string, customerId: string): boolean {
    return this.db.prepare('SELECT 1 FROM redemptions WHERE code = ? AND customer_id = ?').get(code, customerId) !== undefined;
  }

  recordRedemption(code: string, customerId: string): void {
    this.db.prepare('INSERT INTO redemptions VALUES (?, ?)').run(code, customerId);
  }

  insertOrder(o: StoredOrder): void {
    this.db
      .prepare('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)')
      .run(o.id, o.customerId, o.email, o.totalCents, o.couponCode, o.createdAt);
  }

  getOrder(id: string): StoredOrder | undefined {
    const row = this.db.prepare('SELECT * FROM orders WHERE id = ?').get(id) as
      | { id: string; customer_id: string; email: string; total_cents: number; coupon_code: string | null; created_at: string }
      | undefined;
    return (
      row && {
        id: row.id,
        customerId: row.customer_id,
        email: row.email,
        totalCents: row.total_cents,
        couponCode: row.coupon_code,
        createdAt: row.created_at,
      }
    );
  }

  inTransaction<T>(fn: () => T): T {
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const result = fn();
      this.db.exec('COMMIT');
      return result;
    } catch (err) {
      this.db.exec('ROLLBACK');
      throw err;
    }
  }

  close(): void {
    this.db.close();
  }
}
