import { PublicKey } from "@solana/web3.js";
import { Ctx } from "../../types";
import * as accs from "../accounts";
import { TOKEN_PROGRAM_ID } from "@project-serum/serum/lib/token-instructions";
import { toBN, tryGet } from "../../utils";
import { inject } from "../../utils/meta-utils";
export function swap(ctx: Ctx) {
  return async (
    amountIn: bigint,
    minimumAmountOut: bigint,
    lpTokenMint: PublicKey, // TODO: do we have to pass this?
    userFromToken: PublicKey,
    userToToken: PublicKey
  ) => {
    const program = ctx.programs.hydraLiquidityPools;
    const accounts = inject(accs, ctx);
    const { tokenXVault, tokenYVault, poolState } =
      await accounts.getAccountLoaders(lpTokenMint);

    await program.rpc.swap(toBN(amountIn), toBN(minimumAmountOut), {
      accounts: {
        user: ctx.provider.wallet.publicKey,
        poolState: await poolState.key(),
        lpTokenMint,
        userFromToken,
        userToToken,
        tokenXVault: await tokenXVault.key(),
        tokenYVault: await tokenYVault.key(),
        tokenProgram: TOKEN_PROGRAM_ID,
      },
    });
  };
}