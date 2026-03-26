# Wallet Testing Patterns (Web3 / MetaMask)

Patterns for testing Web3 wallet interactions via `addInitScript`.
Used when your application integrates with MetaMask or similar browser-extension wallets.

---

## Mock MetaMask with addInitScript

```typescript
// pages/Web3Page.ts
import { type Page, type Locator } from '@playwright/test';

export class Web3Page {
  readonly page: Page;
  readonly connectWalletButton: Locator;
  readonly walletAddress: Locator;
  readonly txStatus: Locator;

  constructor(page: Page) {
    this.page = page;
    this.connectWalletButton = page.getByTestId('wallet-connect');
    this.walletAddress       = page.getByTestId('wallet-address');
    this.txStatus            = page.getByTestId('tx-status');
  }

  async injectMockEthereum(address = '0xABC123...') {
    await this.page.addInitScript((addr) => {
      (window as any).ethereum = {
        isMetaMask: true,
        selectedAddress: addr,
        request: async ({ method }: { method: string }) => {
          if (method === 'eth_requestAccounts') return [addr];
          if (method === 'eth_accounts') return [addr];
          if (method === 'eth_chainId') return '0x1';
          if (method === 'eth_sendTransaction') return '0xMOCK_TX_HASH';
          return null;
        },
        on: () => {},
        removeListener: () => {},
      };
    }, address);
  }

  async goto() {
    await this.injectMockEthereum();
    await this.page.goto('/app');
    await this.page.waitForLoadState('networkidle');
  }
}
```

```typescript
// tests/e2e/features/wallet.spec.ts
import { test, expect } from '@playwright/test';
import { Web3Page } from '../../../pages/Web3Page';

test.describe('Wallet Connection', () => {
  test('connects wallet and displays address', async ({ page }) => {
    const web3 = new Web3Page(page);
    await web3.goto();
    await web3.connectWalletButton.click();
    await expect(web3.walletAddress).toContainText('0xABC');
  });
});
```

---

## Notes

- `addInitScript` runs before page scripts — the mock is available when the app initialises.
- For transaction hash assertions, use the mock return value `0xMOCK_TX_HASH`.
- Do NOT run wallet tests against real networks — always use mocks or local hardhat/anvil nodes.
