# Subnet Allocation and Network Access Control (Task 5)

## 1. Network Address Block Allocation

- **Parent Block:** `10.20.0.0/16`
- **Total Address Space:** $2^{32-16} = 2^{16} = 65,536$ addresses
- **Allocation Strategy:** Largest requirement to smallest, starting at `10.20.0.0`, contiguously packed with the smallest prefix that satisfies each requirement.
- **Formula for Usable Hosts:** $\text{Usable Hosts} = 2^{32 - \text{prefix}} - 2$

---

### Step-by-Step Derivation

1. **Subnet 1: `app` (Requirement: 1,000 hosts)**
   - Need $2^h - 2 \ge 1000 \implies 2^h \ge 1002 \implies h = 10$ ($2^{10} = 1024, 1024 - 2 = 1022$).
   - Prefix length $= 32 - 10 = /22$.
   - Network address: `10.20.0.0/22`.
   - Host capacity: 1024 addresses (4 class C blocks: `10.20.0.0` through `10.20.3.255`).
   - Usable range: `10.20.0.1` – `10.20.3.254`.
   - Broadcast address: `10.20.3.255`.

2. **Subnet 2: `public` (Requirement: 250 hosts)**
   - Begins immediately after `app`: `10.20.4.0`.
   - Need $2^h - 2 \ge 250 \implies 2^h \ge 252 \implies h = 8$ ($2^8 = 256, 256 - 2 = 254$).
   - Prefix length $= 32 - 8 = /24$.
   - Network address: `10.20.4.0/24`.
   - Host capacity: 256 addresses (`10.20.4.0` through `10.20.4.255`).
   - Usable range: `10.20.4.1` – `10.20.4.254`.
   - Broadcast address: `10.20.4.255`.

3. **Subnet 3: `data` (Requirement: 100 hosts)**
   - Begins immediately after `public`: `10.20.5.0`.
   - Need $2^h - 2 \ge 100 \implies 2^h \ge 102 \implies h = 7$ ($2^7 = 128, 128 - 2 = 126$).
   - Prefix length $= 32 - 7 = /25$.
   - Network address: `10.20.5.0/25`.
   - Host capacity: 128 addresses (`10.20.5.0` through `10.20.5.127`).
   - Usable range: `10.20.5.1` – `10.20.5.126`.
   - Broadcast address: `10.20.5.127`.

4. **Subnet 4: `management` (Requirement: 20 hosts)**
   - Begins immediately after `data`: `10.20.5.128`.
   - Need $2^h - 2 \ge 20 \implies 2^h \ge 22 \implies h = 5$ ($2^5 = 32, 32 - 2 = 30$).
   - Prefix length $= 32 - 5 = /27$.
   - Network address: `10.20.5.128/27`.
   - Host capacity: 32 addresses (`10.20.5.128` through `10.20.5.159`).
   - Usable range: `10.20.5.129` – `10.20.5.158`.
   - Broadcast address: `10.20.5.159`.

---

### Subnet Allocation Table

| Subnet Name | Hosts Needed | Network Address | Prefix Length | Usable Host Range | Broadcast Address | Usable Hosts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **app** | 1,000 | `10.20.0.0` | `/22` | `10.20.0.1` – `10.20.3.254` | `10.20.3.255` | 1,022 |
| **public** | 250 | `10.20.4.0` | `/24` | `10.20.4.1` – `10.20.4.254` | `10.20.4.255` | 254 |
| **data** | 100 | `10.20.5.0` | `/25` | `10.20.5.1` – `10.20.5.126` | `10.20.5.127` | 126 |
| **management** | 20 | `10.20.5.128` | `/27` | `10.20.5.129` – `10.20.5.158` | `10.20.5.159` | 30 |

---

## 2. NACL Architecture and Reasoning

### Why a Stateless NACL Requires Explicit Reply Rules
Unlike stateful firewalls (such as AWS Security Groups or iptables with `conntrack`), a Network Access Control List (NACL) is completely **stateless**. It evaluates each packet individually in isolation with zero memory of preceding packets or existing TCP connection handshakes (`SYN`, `SYN-ACK`, `ACK`).
- When an external client initiates an inbound HTTP/HTTPS request, the packet arrives with a destination port of 80 or 443 and an ephemeral source port (1024–65535). The inbound NACL rule permits this incoming traffic.
- When the server transmits the HTTP response back to the client, the outgoing packet has a source port of 80/443 and a destination port equal to the client's ephemeral port.
- Because the NACL maintains no connection tracking table, it does not recognize that this outbound packet is part of an already-approved bidirectional session.
- Without an explicit **outbound rule** permitting traffic destined to ephemeral ports `1024-65535` across `0.0.0.0/0`, the response packet would encounter the default deny and be dropped, terminating the connection.
- Similarly, when the public load balancer initiates connections to the backend application servers in `app` (`10.20.0.0/22:8000`), the load balancer acts as a client using local ephemeral ports. For the application servers' replies to re-enter the public subnet, an explicit **inbound rule** allowing traffic from `10.20.0.0/22` destined to ephemeral ports `1024-65535` is mandatory.

### Why Rule Order Matters for the `198.51.100.0/24` Abusive Block
NACL rules are evaluated sequentially in strictly ascending order by rule number:
1. **First-Match Semantics:** As soon as an evaluated packet satisfies the criteria of a rule (protocol, port range, CIDR match), the associated action (`allow` or `deny`) is immediately executed, and evaluation terminates.
2. **Precedence of Specific Denial over General Allowance:**
   - To completely drop traffic from the abusive block `198.51.100.0/24` (including attempts on standard web ports like 80 and 443), the block rule **must** be assigned a lower rule number (e.g., Rule 50) than the general rules allowing web traffic from `0.0.0.0/0` (Rules 100 and 110).
   - If the general allow rule `0.0.0.0/0` on port 443 were numbered 100 and the deny rule for `198.51.100.0/24` numbered 200, an incoming packet from `198.51.100.9` on port 443 would match rule 100 first. The packet would be allowed in, entirely bypassing the deny rule.
   - Therefore, specific deny rules must always precede broader allow rules in the rule hierarchy.
