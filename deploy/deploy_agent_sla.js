import fs from 'fs';
import path from 'path';

export default async function deploy(client) {
  console.log("Client connected to chain:", client.chain?.name, "ID:", client.chain?.id);
  console.log("Deployer address:", client.account?.address);

  const contractPath = path.resolve('contracts/agent_sla.py');
  const code = fs.readFileSync(contractPath, 'utf8');
  console.log("Contract code length:", code.length, "bytes");

  console.log("Deploying AgentSLA to GenLayer Testnet Bradbury...");
  const txHash = await client.deployContract({
    code,
    args: [],
    leaderOnly: false,
  });
  console.log("Deployment submitted! Consensus Tx ID / EVM Tx Hash:", txHash);

  console.log("Waiting for transaction consensus receipt...");
  const receipt = await client.waitForTransactionReceipt({
    hash: txHash,
    retries: 80,
    interval: 5000,
    waitUntil: "decided",
    fullTransaction: true
  });
  console.log("=== Deployment Receipt ===");
  console.log("Status:", receipt.statusName ?? receipt.status);
  console.log("Result:", receipt.resultName ?? receipt.result);
  const contractAddress = receipt.data?.contract_address ?? receipt.txDataDecoded?.contractAddress ?? receipt.contractAddress ?? receipt.recipient;
  console.log("Contract Address:", contractAddress);
  return receipt;
}
