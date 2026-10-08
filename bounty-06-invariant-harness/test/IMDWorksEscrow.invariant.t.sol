// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

import {Test} from "forge-std/Test.sol";
import {StdInvariant} from "forge-std/StdInvariant.sol";
import {IMDWorksEscrow} from "../src/IMDWorksEscrow.sol";
import {MockUSDG} from "../src/MockUSDG.sol";

contract EscrowHandler is Test {
    IMDWorksEscrow public immutable escrow;
    MockUSDG public immutable token;
    address[3] public creators;
    address[5] public workers;

    struct ModelBounty {
        address creator;
        uint256 reward;
        uint64 deadline;
        uint8 status; // mirrors Missing/Open/Awarded/Cancelled/Expired
        uint8 submissions;
        address winner;
        uint8 terminalTransitions;
    }

    ModelBounty[] internal model;
    mapping(uint256 => mapping(address => bool)) public submitted;
    mapping(address => uint256) public modelClaimable;
    uint256 public modelLocked;
    uint256 public modelTotalClaimable;

    constructor(IMDWorksEscrow escrow_, MockUSDG token_) {
        escrow = escrow_;
        token = token_;
        creators = [address(0xC001), address(0xC002), address(0xC003)];
        workers = [address(0xA001), address(0xA002), address(0xA003), address(0xA004), address(0xA005)];
        model.push(); // bounty IDs start at one
        for (uint256 i; i < creators.length; ++i) {
            token.mint(creators[i], 1_000_000_000e18);
            vm.prank(creators[i]); token.approve(address(escrow), type(uint256).max);
        }
    }

    function create(uint256 creatorSeed, uint96 rawReward, uint32 rawDuration) external {
        if (model.length >= 33) return;
        address creator = creators[creatorSeed % creators.length];
        uint256 reward = bound(uint256(rawReward), 1, 1_000_000e18);
        uint64 deadline = uint64(block.timestamp + bound(uint256(rawDuration), 1 hours, 90 days));
        vm.prank(creator);
        try escrow.createBounty(reward, deadline, keccak256(abi.encode(model.length)), "ipfs://brief") returns (uint256 id) {
            assertEq(id, model.length);
            model.push(ModelBounty(creator, reward, deadline, 1, 0, address(0), 0));
            modelLocked += reward;
        } catch {}
    }

    function delegate(uint256 workerSeed, uint256 operatorSeed, bool approved) external {
        address author = workers[workerSeed % workers.length];
        address operator = workers[operatorSeed % workers.length];
        if (author == operator) return;
        vm.prank(author); escrow.setOperator(operator, approved);
    }

    function submit(uint256 idSeed, uint256 workerSeed, uint256 operatorSeed, bool delegated) external {
        if (model.length <= 1) return;
        uint256 id = 1 + (idSeed % (model.length - 1));
        address author = workers[workerSeed % workers.length];
        bytes32 proof = keccak256(abi.encode(id, author, block.timestamp, workerSeed));
        if (delegated) {
            address operator = workers[operatorSeed % workers.length];
            vm.prank(operator);
            try escrow.submitWorkFor(id, author, proof, "ipfs://proof") { _recordSubmission(id, author); } catch {}
        } else {
            vm.prank(author);
            try escrow.submitWork(id, proof, "ipfs://proof") { _recordSubmission(id, author); } catch {}
        }
    }

    function topUp(uint256 idSeed, uint96 rawAmount) external {
        if (model.length <= 1) return;
        uint256 id = 1 + (idSeed % (model.length - 1));
        uint256 amount = bound(uint256(rawAmount), 1, 100_000e18);
        vm.prank(model[id].creator);
        try escrow.addReward(id, amount) { model[id].reward += amount; modelLocked += amount; } catch {}
    }

    function jump(uint32 rawSeconds) external {
        vm.warp(block.timestamp + bound(uint256(rawSeconds), 1, 30 days));
    }

    function cancel(uint256 idSeed) external {
        if (model.length <= 1) return;
        uint256 id = 1 + (idSeed % (model.length - 1));
        vm.prank(model[id].creator);
        try escrow.cancel(id) { _terminal(id, 3, model[id].creator); } catch {}
    }

    function award(uint256 idSeed, uint256 workerSeed) external {
        if (model.length <= 1) return;
        uint256 id = 1 + (idSeed % (model.length - 1));
        address winner = workers[workerSeed % workers.length];
        vm.prank(model[id].creator);
        try escrow.award(id, winner) { model[id].winner = winner; _terminal(id, 2, winner); } catch {}
    }

    function expire(uint256 idSeed) external {
        if (model.length <= 1) return;
        uint256 id = 1 + (idSeed % (model.length - 1));
        try escrow.expire(id) { _terminal(id, 4, model[id].creator); } catch {}
    }

    function withdraw(uint256 actorSeed) external {
        address actor = actorSeed % 8 < 3 ? creators[actorSeed % 3] : workers[actorSeed % 5];
        vm.prank(actor);
        try escrow.withdraw(actor) {
            uint256 amount = modelClaimable[actor];
            modelClaimable[actor] = 0;
            modelTotalClaimable -= amount;
        } catch {}
    }

    function modelLiabilities() external view returns (uint256) { return modelLocked + modelTotalClaimable; }
    function bountyCount() external view returns (uint256) { return model.length - 1; }
    function bounty(uint256 id) external view returns (ModelBounty memory) { return model[id]; }

    function _recordSubmission(uint256 id, address author) internal {
        if (!submitted[id][author]) { submitted[id][author] = true; model[id].submissions++; }
    }

    function _terminal(uint256 id, uint8 status, address payee) internal {
        ModelBounty storage b = model[id];
        b.terminalTransitions++;
        b.status = status;
        modelLocked -= b.reward;
        modelTotalClaimable += b.reward;
        modelClaimable[payee] += b.reward;
    }
}

contract IMDWorksEscrowInvariantTest is StdInvariant, Test {
    IMDWorksEscrow internal escrow;
    MockUSDG internal token;
    EscrowHandler internal handler;

    function setUp() public {
        token = new MockUSDG();
        escrow = new IMDWorksEscrow(address(token));
        handler = new EscrowHandler(escrow, token);
        targetContract(address(handler));
    }

    function invariant_balanceCoversIndependentLiabilities() public view {
        uint256 independent = handler.modelLiabilities();
        assertGe(token.balanceOf(address(escrow)), independent);
        assertEq(escrow.liabilities(), independent);
    }

    function invariant_terminalBountyCannotPayTwice() public view {
        uint256 count = handler.bountyCount();
        for (uint256 id = 1; id <= count; ++id) {
            EscrowHandler.ModelBounty memory m = handler.bounty(id);
            assertLe(m.terminalTransitions, 1);
            (address creator,address winner,uint64 deadline,uint64 submissions,IMDWorksEscrow.Status status,uint256 reward,) = escrow.bounties(id);
            assertEq(creator, m.creator); assertEq(winner, m.winner); assertEq(deadline, m.deadline);
            assertEq(submissions, m.submissions); assertEq(uint8(status), m.status); assertEq(reward, m.reward);
        }
    }
}
