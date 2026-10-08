// SPDX-License-Identifier: MIT
pragma solidity 0.8.29;

import {Test} from "forge-std/Test.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IMDWorksEscrow} from "../src/IMDWorksEscrow.sol";
import {ModeToken, ReentrantWinner} from "../src/TokenModeMocks.sol";

contract TokenModesTest is Test {
    ModeToken token;
    IMDWorksEscrow escrow;

    address creator = makeAddr("creator");
    address worker = makeAddr("worker");
    address recipient = makeAddr("recipient");
    uint256 constant REWARD = 100 ether;
    bytes32 constant BRIEF = keccak256("brief");
    bytes32 constant PROOF = keccak256("proof");

    function setUp() public {
        token = new ModeToken();
        escrow = new IMDWorksEscrow(address(token));
        token.mint(creator, 1_000 ether);
        vm.prank(creator);
        token.approve(address(escrow), type(uint256).max);
    }

    function test_standardToken_fullDepositAwardRefundWithdrawalMatrix() public {
        _exerciseSupportedMatrix(false);
    }

    function test_noReturnToken_fullDepositAwardRefundWithdrawalMatrix() public {
        _exerciseSupportedMatrix(true);
    }

    function test_falseReturn_depositRejectedAndStateRolledBack() public {
        token.configureReturns(true, false);
        vm.prank(creator);
        vm.expectRevert(abi.encodeWithSelector(SafeERC20.SafeERC20FailedOperation.selector, address(token)));
        escrow.createBounty(REWARD, _deadline(), BRIEF, "brief");
        assertEq(escrow.nextBountyId(), 1);
        assertEq(escrow.liabilities(), 0);
        assertEq(token.balanceOf(address(escrow)), 0);
    }

    function test_falseReturn_failedWithdrawalPreservesClaimAndIssuerCanRecover() public {
        uint256 id = _awarded(worker);
        assertEq(id, 1);
        token.configureReturns(true, false);
        vm.prank(worker);
        vm.expectRevert(abi.encodeWithSelector(SafeERC20.SafeERC20FailedOperation.selector, address(token)));
        escrow.withdraw(recipient);
        _assertClaim(worker, REWARD);

        token.configureReturns(false, false);
        vm.prank(worker);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();
    }

    function test_transferTax_depositRejectedAsUnsupportedAndStateRolledBack() public {
        token.setTaxBps(100);
        vm.prank(creator);
        vm.expectRevert(IMDWorksEscrow.UnsupportedTransfer.selector);
        escrow.createBounty(REWARD, _deadline(), BRIEF, "brief");
        assertEq(escrow.nextBountyId(), 1);
        assertEq(escrow.liabilities(), 0);
        assertEq(token.balanceOf(address(escrow)), 0);
        assertEq(token.balanceOf(creator), 1_000 ether);
    }

    function test_transferTax_failedWithdrawalPreservesClaimAndIssuerCanRecover() public {
        _awarded(worker);
        token.setTaxBps(100);
        vm.prank(worker);
        vm.expectRevert(IMDWorksEscrow.UnsupportedTransfer.selector);
        escrow.withdraw(recipient);
        _assertClaim(worker, REWARD);
        assertEq(token.balanceOf(recipient), 0);
        _assertConserved();

        token.setTaxBps(0);
        vm.prank(worker);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();
    }

    function test_pause_doesNotPreventAwardBookkeepingAndRecoveryWithdrawal() public {
        uint256 id = _openWithSubmission(worker);
        token.setPaused(true);
        vm.prank(creator);
        escrow.award(id, worker);
        _assertStatus(id, IMDWorksEscrow.Status.Awarded);
        _assertClaim(worker, REWARD);
        _assertConserved();

        vm.prank(worker);
        vm.expectRevert(bytes("paused"));
        escrow.withdraw(recipient);
        _assertClaim(worker, REWARD);

        token.setPaused(false);
        vm.prank(worker);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();
    }

    function test_pause_doesNotPreventCancelRefundBookkeepingAndRecoveryWithdrawal() public {
        uint256 id = _create(REWARD);
        token.setPaused(true);
        vm.prank(creator);
        escrow.cancel(id);
        _assertStatus(id, IMDWorksEscrow.Status.Cancelled);
        _assertClaim(creator, REWARD);
        _assertConserved();

        vm.prank(creator);
        vm.expectRevert(bytes("paused"));
        escrow.withdraw(recipient);
        _assertClaim(creator, REWARD);

        token.setPaused(false);
        vm.prank(creator);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();
    }

    function test_pause_doesNotPreventExpireRefundBookkeeping() public {
        uint256 id = _create(REWARD);
        token.setPaused(true);
        vm.warp(_bountyDeadline(id));
        escrow.expire(id);
        _assertStatus(id, IMDWorksEscrow.Status.Expired);
        _assertClaim(creator, REWARD);
        _assertConserved();
    }

    function test_senderRestriction_depositRejectedThenIssuerUnblocksAndDepositSucceeds() public {
        token.setBlockedSender(creator, true);
        vm.prank(creator);
        vm.expectRevert(bytes("sender blocked"));
        escrow.createBounty(REWARD, _deadline(), BRIEF, "brief");
        assertEq(escrow.liabilities(), 0);

        token.setBlockedSender(creator, false);
        uint256 id = _create(REWARD);
        _assertStatus(id, IMDWorksEscrow.Status.Open);
        _assertConserved();
    }

    function test_senderRestriction_onEscrowPreservesClaimThenIssuerUnblocks() public {
        _awarded(worker);
        token.setBlockedSender(address(escrow), true);
        vm.prank(worker);
        vm.expectRevert(bytes("sender blocked"));
        escrow.withdraw(recipient);
        _assertClaim(worker, REWARD);

        token.setBlockedSender(address(escrow), false);
        vm.prank(worker);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();
    }

    function test_recipientRestriction_depositRejectedThenIssuerUnblocks() public {
        token.setBlockedRecipient(address(escrow), true);
        vm.prank(creator);
        vm.expectRevert(bytes("recipient blocked"));
        escrow.createBounty(REWARD, _deadline(), BRIEF, "brief");
        assertEq(escrow.liabilities(), 0);

        token.setBlockedRecipient(address(escrow), false);
        _create(REWARD);
        _assertConserved();
    }

    function test_recipientRestriction_failedWithdrawalPreservesClaimThenIssuerUnblocks() public {
        _awarded(worker);
        token.setBlockedRecipient(recipient, true);
        vm.prank(worker);
        vm.expectRevert(bytes("recipient blocked"));
        escrow.withdraw(recipient);
        _assertClaim(worker, REWARD);

        token.setBlockedRecipient(recipient, false);
        vm.prank(worker);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();
    }

    function test_falseReturn_postDepositAwardRefundAndWithdrawalRecovery() public {
        _postDepositAwardRefundMatrix(1);
    }

    function test_transferTax_postDepositAwardRefundAndWithdrawalRecovery() public {
        _postDepositAwardRefundMatrix(2);
    }

    function test_pause_postDepositAwardRefundAndWithdrawalRecovery() public {
        _postDepositAwardRefundMatrix(3);
    }

    function test_senderRestriction_postDepositAwardRefundAndWithdrawalRecovery() public {
        _postDepositAwardRefundMatrix(4);
    }

    function test_recipientRestriction_postDepositAwardRefundAndWithdrawalRecovery() public {
        _postDepositAwardRefundMatrix(5);
    }

    function test_depositCallbackCannotReenterCreateBounty() public {
        bytes memory nested = abi.encodeCall(escrow.createBounty, (1 ether, _deadline(), keccak256("nested"), "nested"));
        token.setCallback(address(escrow), nested, true, false);
        uint256 id = _create(REWARD);
        assertEq(id, 1);
        assertEq(escrow.nextBountyId(), 2);
        assertEq(token.callbackCount(), 1);
        assertFalse(token.lastCallbackSuccess());
        assertEq(token.lastCallbackError(), ReentrancyGuard.ReentrancyGuardReentrantCall.selector);
        _assertConserved();
    }

    function test_withdrawCallbackCannotReenterAndOuterWithdrawalConservesBalance() public {
        ReentrantWinner winner = new ReentrantWinner(address(escrow), recipient);
        uint256 id = _create(REWARD);
        winner.submit(id, PROOF, "proof");
        vm.prank(creator);
        escrow.award(id, address(winner));

        token.setCallback(address(winner), abi.encodeCall(winner.attackWithdraw, ()), false, true);
        winner.withdraw();

        assertEq(token.callbackCount(), 1);
        assertFalse(winner.nestedSucceeded());
        assertEq(winner.nestedError(), ReentrancyGuard.ReentrancyGuardReentrantCall.selector);
        assertEq(token.balanceOf(recipient), REWARD);
        assertEq(escrow.claimable(address(winner)), 0);
        _assertConserved();
    }

    function test_balanceConservationAcrossTwoBountiesPartialLifecycle() public {
        uint256 awardedId = _openWithSubmission(worker);
        uint256 cancelledId = _create(40 ether);
        vm.prank(creator);
        escrow.award(awardedId, worker);
        vm.prank(creator);
        escrow.cancel(cancelledId);
        assertEq(escrow.totalLocked(), 0);
        assertEq(escrow.totalClaimable(), 140 ether);
        _assertConserved();

        vm.prank(worker);
        escrow.withdraw(worker);
        assertEq(escrow.totalClaimable(), 40 ether);
        _assertConserved();
        vm.prank(creator);
        escrow.withdraw(creator);
        _assertConserved();
    }

    function _postDepositAwardRefundMatrix(uint8 mode) private {
        uint256 awardId = _openWithSubmission(worker);
        uint256 refundId = _create(40 ether);
        _enablePostDepositMode(mode);

        vm.prank(creator);
        escrow.award(awardId, worker);
        vm.prank(creator);
        escrow.cancel(refundId);
        _assertStatus(awardId, IMDWorksEscrow.Status.Awarded);
        _assertStatus(refundId, IMDWorksEscrow.Status.Cancelled);
        assertEq(escrow.claimable(worker), REWARD);
        assertEq(escrow.claimable(creator), 40 ether);
        assertEq(escrow.totalClaimable(), 140 ether);
        _assertConserved();

        vm.prank(worker);
        if (mode == 1) {
            vm.expectRevert(abi.encodeWithSelector(SafeERC20.SafeERC20FailedOperation.selector, address(token)));
        } else if (mode == 2) {
            vm.expectRevert(IMDWorksEscrow.UnsupportedTransfer.selector);
        } else if (mode == 3) {
            vm.expectRevert(bytes("paused"));
        } else if (mode == 4) {
            vm.expectRevert(bytes("sender blocked"));
        } else {
            vm.expectRevert(bytes("recipient blocked"));
        }
        escrow.withdraw(recipient);
        assertEq(escrow.claimable(worker), REWARD);
        assertEq(escrow.totalClaimable(), 140 ether);
        _assertConserved();

        _disablePostDepositMode(mode);
        vm.prank(worker);
        escrow.withdraw(recipient);
        vm.prank(creator);
        escrow.withdraw(creator);
        assertEq(token.balanceOf(recipient), REWARD);
        assertEq(escrow.totalClaimable(), 0);
        _assertConserved();
    }

    function _enablePostDepositMode(uint8 mode) private {
        if (mode == 1) token.configureReturns(true, false);
        else if (mode == 2) token.setTaxBps(100);
        else if (mode == 3) token.setPaused(true);
        else if (mode == 4) token.setBlockedSender(address(escrow), true);
        else token.setBlockedRecipient(recipient, true);
    }

    function _disablePostDepositMode(uint8 mode) private {
        if (mode == 1) token.configureReturns(false, false);
        else if (mode == 2) token.setTaxBps(0);
        else if (mode == 3) token.setPaused(false);
        else if (mode == 4) token.setBlockedSender(address(escrow), false);
        else token.setBlockedRecipient(recipient, false);
    }

    function _exerciseSupportedMatrix(bool noReturn) private {
        token.configureReturns(false, noReturn);
        uint256 awardedId = _openWithSubmission(worker);
        vm.prank(creator);
        escrow.award(awardedId, worker);
        _assertStatus(awardedId, IMDWorksEscrow.Status.Awarded);
        _assertClaim(worker, REWARD);
        _assertConserved();
        vm.prank(worker);
        escrow.withdraw(recipient);
        assertEq(token.balanceOf(recipient), REWARD);
        _assertConserved();

        uint256 refundId = _create(40 ether);
        vm.prank(creator);
        escrow.cancel(refundId);
        _assertStatus(refundId, IMDWorksEscrow.Status.Cancelled);
        _assertClaim(creator, 40 ether);
        _assertConserved();
        uint256 beforeCreator = token.balanceOf(creator);
        vm.prank(creator);
        escrow.withdraw(creator);
        assertEq(token.balanceOf(creator), beforeCreator + 40 ether);
        _assertConserved();
    }

    function _awarded(address winner) private returns (uint256 id) {
        id = _openWithSubmission(winner);
        vm.prank(creator);
        escrow.award(id, winner);
        _assertConserved();
    }

    function _openWithSubmission(address submitter) private returns (uint256 id) {
        id = _create(REWARD);
        vm.prank(submitter);
        escrow.submitWork(id, PROOF, "proof");
    }

    function _create(uint256 amount) private returns (uint256 id) {
        vm.prank(creator);
        id = escrow.createBounty(amount, _deadline(), BRIEF, "brief");
        _assertConserved();
    }

    function _deadline() private view returns (uint64) {
        return uint64(block.timestamp + 2 hours);
    }

    function _bountyDeadline(uint256 id) private view returns (uint64 deadline) {
        (,, deadline,,,,) = escrow.bounties(id);
    }

    function _assertStatus(uint256 id, IMDWorksEscrow.Status expected) private view {
        (,,,, IMDWorksEscrow.Status status,,) = escrow.bounties(id);
        assertEq(uint256(status), uint256(expected));
    }

    function _assertClaim(address account, uint256 expected) private view {
        assertEq(escrow.claimable(account), expected);
        assertEq(escrow.totalClaimable(), expected);
        _assertConserved();
    }

    function _assertConserved() private view {
        assertEq(token.balanceOf(address(escrow)), escrow.liabilities());
        assertEq(escrow.liabilities(), escrow.totalLocked() + escrow.totalClaimable());
    }
}
