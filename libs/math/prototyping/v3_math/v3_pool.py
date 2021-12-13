"""
Classes to conceptualize the workings of an AMM v3  liquiditiy pool
based on :
  * Uniswap v3 core paper
  * Liquidity Math in Uniswap v3 - Technical Note
"""
import math
from dataclasses import dataclass


@dataclass
class Token:
    name: str
    decimals: int


@dataclass
class GlobalState:
    """contract global state"""

    L: float = 0.0  # liquidity
    rP: float = 0.0  # sqrt price
    tick: int = 0  # current tick
    fg_x: float = 0.0  # fee growth global
    fg_y: float = 0.0  # fee growth global
    proto_x: float = 0.0  # protocol fees
    proto_y: float = 0.0  # protocol fees


@dataclass
class TickState:
    """Tick Indexed State"""

    liq_net: float = 0.0  # LiquidityNet
    liq_gross: float = 0.0  # LiquidityGross
    f0_x: float = 0.0  # feegrowth outside
    f0_y: float = 0.0  # feegrowth outside
    # TODO : implem s0, i0, sl0 in Tick-state
    s0_x: float = 0.0  # seconds (time) outside
    s0_y: float = 0.0  # seconds (time) outside
    i0_x: float = 0.0  # tickCumulative outside
    i0_y: float = 0.0  # tickCumulative outside
    sl0_x: float = 0.0  # secondsPerLiqudity outside
    sl0_y: float = 0.0  # secondsPerLiqudity outside


@dataclass
class PositionState:
    """Position Indexed State"""

    liq: float = 0.0  # liquidity
    fr_x: float = 0.0  # feegrowth inside last
    fr_y: float = 0.0  # feegrowth inside last


class Pool:
    """AMM pool with concentrated liquidity
    tokens X and Y, prices expressed with Y as numeraire"""

    TICK_BASE = 1.0001

    def __init__(
        self,
        x_name,
        x_decimals,
        y_name,
        y_decimals,
        bootstrap_rP,
        tick_spacing: int = 1,
    ):
        self.token_x = Token(x_name, x_decimals)
        self.token_y = Token(y_name, y_decimals)
        # only tick multiple of spacing are allowed
        self.tick_spacing = tick_spacing

        self.global_state = GlobalState(
            rP=bootstrap_rP,
            tick=self.rP_to_possible_tick(bootstrap_rP, left_to_right=False),
        )

        # * initialized ticks, keys are the tick i itself
        self.active_ticks = {}  # {i: TickState() for i in range(5)}
        # * positions are indexed by ( user_id, lower_tick, upper_tick):
        self.positions = {}
        # real reserves
        self.X, self.Y = 0.0, 0.0

    def name(self):
        name = f"{self.token_x.name}-{self.token_y.name} pool"
        return f"{name} - tick spacing {self.tick_spacing}"

    def __repr__(self):
        lines = []
        lines.append(f"{self.name()}")
        lines.append(f"{self.token_x} {self.token_y}")
        lines.append(f"{repr(self.global_state)}")
        lines.append(f"real reserve X={self.X} Y={self.Y}")
        lines.append(
            "\n".join(
                [repr(tick) for tick in list(self.active_ticks.values())[:10]]
            )
        )
        lines.append(
            "\n".join(
                [repr(poz) for poz in list(self.positions.values())[:10]]
            )
        )

        return "\n".join(lines)

    def show(self):
        print(f"{self.global_state}\nreal reserves X={self.X} Y={self.Y}")
        print("---active ticks---")
        for k, v in self.active_ticks.items():
            print(f"tick '{k}': {v}")
        print("---positions---")
        for k, v in self.positions.items():
            print(f"poz '{k}': {v}")

    @staticmethod
    def liq_x_only(x, rPa, rPb):
        """Lx : liquidity amount when liquidity fully composed of  token x
        e.g when price below lower bound of range and y=0. [5]
            x : token x real reserves
            rPa,rPb : range lower (upper) bound in root price
        """
        return x * rPa * rPb / (rPb - rPa)

    @staticmethod
    def liq_y_only(y, rPa, rPb):
        """Ly : liquidity amount when liquidity fully composed of  token y
        e.g when price above upper bound of range, x=0. [9]
            y : token y real reserves
            rPa,rPb : range lower (upper) bound in root price
        """
        return y / (rPb - rPa)

    @staticmethod
    def liq_from_x_y_rP_rng(x, y, rP, rPa, rPb):
        """L : liquidity amount from real reserves based on
        where price is compared to price range
            x,y : real token reserves
            rPa,rPb : range lower (upper) bound in root price
            rP : current root price
        """
        if rP <= rPa:
            # y = 0 and reserves entirely in x. [4]
            return Pool.liq_x(x, rPa, rPb)
        elif rP < rPb:  # [11,12]
            # x covers sub-range [P,Pb] and y covers the other side [Pa,P]
            Lx = Pool.liq_x_only(x, rP, rPb)
            Ly = Pool.liq_y_only(y, rPa, rP)
            # Lx Ly should be close to equal, by precaution take the minimum
            return min(Lx, Ly)
        else:
            # x = 0 and reserves entirely in y. [8]
            return Pool.liq_y_only(y, rPa, rPb)

    @staticmethod
    def x_from_L_rP_rng(L, rP, rPa, rPb):
        """calculate X amount from L, price and bounds"""
        # if the price is outside the range, use range endpoints instead [11]
        rP = max(min(rP, rPb), rPa)
        return L * (rPb - rP) / (rP * rPb)

    @staticmethod
    def y_from_L_rP_rng(L, rP, rPa, rPb):
        """calculate Y amount from L, price and bounds"""
        # if the price is outside the range, use range endpoints instead [12]
        rP = max(min(rP, rPb), rPa)
        return L * (rP - rPa)

    # bounds in 2-steps calc, after getting Liquidity
    @staticmethod
    def rPa_from_L_rP_y(L, rP, y):
        """lower bound from L, price and y amount [13]"""
        return rP - (y / L)

    @staticmethod
    def rPb_from_L_rP_x(L, rP, y):
        """upper bound from L, price and x amount [14]"""
        return rP - (y / L)

    # bounds in 1-step calc, from real reserves
    @staticmethod
    def rPa_from_x_y_rP_rPb(x, y, rP, rPb):
        """lower bound from x, y amounts, price and upper bound [15]"""
        return (y / (rPb * x)) + rP - (y / (rP * x))

    @staticmethod
    def rPb_from_x_y_rP_rPa(x, y, rP, rPa):
        """upper bound from x, y amounts, price and lower bound [16]"""
        return (rP * y) / ((rPa - rP) * rP * x + y)

    @staticmethod
    def dX_from_L_drP(L, rP_old, rP_new):
        """Change of reserve X based of change of price"""
        return L * (1 / rP_new - 1 / rP_old)

    @staticmethod
    def dY_from_L_drP(L, rP_old, rP_new):
        """Change of reserve Y based of change of price"""
        return L * (rP_new - rP_old)

    @staticmethod
    def rP_new_from_L_dX(L, rP_old, dX):
        """new price based of change of reserve X"""
        drP_inv = dX / L
        return 1 / (drP_inv + 1 / rP_old)

    @staticmethod
    def rP_new_from_L_dY(L, dY, rP_old):
        """new price based of change of reserve Y"""
        return dY / L + rP_old

    @staticmethod
    def tick_to_rP(tick):
        return Pool.TICK_BASE ** (tick / 2)

    @staticmethod
    def rP_to_tick(rP, left_to_right=False):
        d = math.pow(Pool.TICK_BASE, 1 / 2)
        if left_to_right is True:
            return math.ceil(math.log(rP, d))
        else:
            return math.floor(math.log(rP, d))

    def tick_to_possible_tick(self, tick, left_to_right=False):
        # use self.tick_spacing to find allowable tick that is <= tick_lower
        #  unchanged if self.tick_spacing is 1
        if left_to_right is True:
            return math.ceil(tick / self.tick_spacing) * self.tick_spacing
        else:
            return math.floor(tick / self.tick_spacing) * self.tick_spacing

    def rP_to_possible_tick(self, rP, left_to_right=False):
        # find allowable tick that is <= tick_theo, from given rP
        tick_theo = Pool.rP_to_tick(rP, left_to_right)
        return self.tick_to_possible_tick(tick_theo, left_to_right)

    def initialize_tick(self, tick: int) -> TickState:
        # set f0 of tick based on convention [6.21]
        f0_x = self.global_state.fg_x if self.global_state.tick >= tick else 0
        f0_y = self.global_state.fg_y if self.global_state.tick >= tick else 0
        # TODO : to the same to s0, i0 and sl0 of tick state

        ts = TickState(f0_x=f0_x, f0_y=f0_y)
        self.active_ticks[tick] = ts

        return ts

    def unset_tick(self, tick):
        del self.active_ticks[tick]

    def update_tick(self, tick: int, liq_delta, upper=False):
        """Update specific tick's liquidity delta for specific tick"""
        # get the tick state for tick if exists, else initialize one
        ts: TickState = self.active_ticks.get(
            tick, None
        ) or self.initialize_tick(tick)

        ts.liq_net += liq_delta if not upper else -liq_delta
        ts.liq_gross += liq_delta

        if ts.liq_gross == 0.0:
            # de-initialize tick when no longer ref'ed by a position
            self.unset_tick(tick)

    def get_next_active_tick_left(self, starting_rP):
        """get next available active tick from a starting point going left"""
        start_tick = self.rP_to_possible_tick(starting_rP, left_to_right=False)
        for tk in sorted(self.active_ticks.keys(), key=None, reverse=True):
            if tk <= start_tick:
                # case when  starting_rP equals exactly tick_torP(current tick)
                #  is covered in swap method (will do 0-qty and trigger cross)
                return tk
            # ignore ticks above current tick
            continue

        # if we get here then no active tick left
        return None

    def get_next_active_tick_right(self, starting_rP):
        """get next available active tick from a starting point going right"""
        pass

    def try_get_in_range(self, left_to_right=False):
        """During swap, when no liquidity in current state, find next active
        tick, cross it to kick-in some liquidity. return tick and rP.
        If no active tick left return None, _"""
        if self.global_state.L > 0.0:
            raise Exception("there already is liquidity in range")

        if not left_to_right:
            for tk in sorted(self.active_ticks.keys(), key=None, reverse=True):
                if tk > self.global_state.tick:
                    # ignore ticks above current tick
                    continue
                self.global_state.tick = tk
                self.global_state.rP = Pool.tick_to_rP(tk)
                self.cross_tick(tk, left_to_right=False)
                # at this point some Liquidity should have kicked in
                if self.global_state.L < 0.0:
                    raise Exception(
                        """from being out of range, we don't expect to kick in
                         negative liquidity"""
                    )
                if self.global_state.L > 0.0:
                    return self.global_state.tick, self.global_state.rP
        return None, self.global_state.rP

    def cross_tick(self, provided_tick, left_to_right=True):
        """Handle update of global state and tick state when
        initialized tick is crossed while performing swap"""

        # TODO check if provided tick matches curr tick
        if not left_to_right and self.global_state.tick != provided_tick:
            raise Exception("can only cross current tick")

        # Get the liquidity delta from tick
        ts: TickState = self.active_ticks.get(provided_tick, None)
        if ts is None:
            raise Exception("cannot find tick for crossing")

        # add/substract to glabal liq depending on direction of crossing
        liq_to_apply = ts.liq_net if left_to_right else -ts.liq_net
        if self.global_state.L + liq_to_apply < 0.0:
            raise Exception("liquidity cannot turn negative")
        self.global_state.L += liq_to_apply

        # update tick state by flipping fee growth outside f0_X_Y [6.26]
        ts.f0_x = self.global_state.fg_x - ts.f0_x
        ts.f0_y = self.global_state.fg_y - ts.f0_y

        # TODO: do the same for s0, i0, sl0 in Tick-state

        # update current tick in global state to reflect crossing; rP unchanged
        if left_to_right is True:
            self.global_state.tick = self.tick_to_possible_tick(
                provided_tick + 1, left_to_right
            )
        else:
            self.global_state.tick = self.tick_to_possible_tick(
                provided_tick - 1, left_to_right
            )

    def _set_position(self, user_id, lower_tick, upper_tick, liq_delta):
        """handles all facets for updates a position for in the pool,
        used for deposits (l>0), withdrawals (l<0)"""
        # TODO :compute the uncollected fees f_u the poz is entitled to
        new_fr_x, new_fr_y = 0.0, 0.0

        # find position if exists
        # positions are uniquely identitfied by the (sender, lower, upper)
        key = (user_id, lower_tick, upper_tick)
        poz: PositionState = self.positions.get(key, None)

        if poz is None:
            if liq_delta < 0.0:
                # abort if withdrawal liq exceeds position liquidity
                raise Exception("cannot newly provide negative liquidity")
            # creates a new position
            self.positions[key] = PositionState(
                liq=liq_delta, fr_x=0.0, fr_y=0.0
            )
        else:
            # update existing position
            if liq_delta < 0.0 and poz.liq + liq_delta < 0.0:
                # abort if withdrawal liq exceeds position liquidity
                raise Exception("liquidity is position insufficient")

            if poz.liq + liq_delta == 0.0:
                # if position liq becomes 0 after operation remove from pool
                del self.positions[key]
            else:
                self.positions[key] = PositionState(
                    liq=poz.liq + liq_delta, fr_x=new_fr_x, fr_y=new_fr_y
                )

        # update tick states for lower and upper
        self.update_tick(lower_tick, liq_delta, upper=False)
        self.update_tick(upper_tick, liq_delta, upper=True)

        # update global state's liquidity if current price in poz's range
        if (
            self.global_state.tick >= lower_tick
            and self.global_state.tick < upper_tick
        ):
            self.global_state.L += liq_delta

    def deposit(self, user_id, x, y, rPa, rPb):
        """interface to deposit liquidity in pool & give change if necessary"""
        rP = self.global_state.rP
        liq = Pool.liq_from_x_y_rP_rng(x, y, rP, rPa, rPb)
        # round down to avoid float rounding vulnerabilities
        liq = math.floor(liq)

        x_dep = Pool.x_from_L_rP_rng(liq, rP, rPa, rPb)
        y_dep = Pool.y_from_L_rP_rng(liq, rP, rPa, rPb)
        # TODO round up amount deposited
        assert x_dep <= x, "used x amt cannot excess provided amount"
        assert y_dep <= y, "used y amt cannot excess provided amount"

        lower_tick = self.rP_to_possible_tick(rPa, left_to_right=False)
        upper_tick = self.rP_to_possible_tick(rPb, left_to_right=False)

        self._set_position(user_id, lower_tick, upper_tick, liq_delta=liq)
        self.X, self.Y = x_dep, y_dep
        print(f"{x_dep=} {y_dep=} X returned {x-x_dep} Y returned {y-y_dep}")

    def withdraw(self, user_id, x, y, rPa, rPb):
        pass

    def swap_within_tick_from_X(self, start_rP, next_tick, L, dX):
        # + no writing to state to occurs here, just calc and return to caller
        done_dX, done_dY, end_rP = 0.0, 0.0, 0.0
        cross: bool = False

        if dX <= 0.0:
            raise Exception("can only handle X being supplied to pool, dX>0")

        # root-price at next tick
        rP_next = self.tick_to_rP(next_tick)
        if rP_next > start_rP:
            raise Exception("expect price to go down when X supplied to pool")
            # we allow case when price exactly on the current tick
            # ( i.e. rP_next > start_rP)
            # this will lead to 0-qty swapped, and crossing before next swap

        # chg of reserve X possible if we go all the way to next tick
        doable_dX = Pool.dX_from_L_drP(L=L, rP_old=start_rP, rP_new=rP_next)
        if doable_dX < 0.0:  # expect a positive number
            raise Exception("doable_dX > 0 when X supplied to pool")

        if doable_dX < dX:
            # we'll have leftover to swap. do what we can. done_X = doableX
            done_dX = doable_dX
            cross = True  # because we'll need to cross and do extra swaps
            end_rP = rP_next  # swap so far moves price to level at this tick
            done_dY = Pool.dY_from_L_drP(L=L, rP_old=start_rP, rP_new=end_rP)
            if done_dY > 0.0:
                raise Exception("expect done_dY > 0 when X supplied to pool")
                # again we allow 0-qty swap, just in case price was already
                # exactly on the tick we started with

            return done_dX, done_dY, end_rP, cross

        else:
            # we have enough, make all dX done, dY, end_rP
            done_dX = dX
            cross = False
            end_rP = Pool.rP_new_from_L_dX(L, start_rP, done_dX)
            if end_rP > start_rP:
                raise Exception("expect end_rP < start_rP when pool given X")
            if end_rP < rP_next:
                raise Exception(
                    "dont expect end_rP go beyond rP_next when filling all dX"
                )
            done_dY = Pool.dY_from_L_drP(L, rP_old=start_rP, rP_new=end_rP)
            if done_dY > 0.0:
                raise Exception("done_dY > 0 when X supplied to pool")

            return done_dX, done_dY, end_rP, cross

    def execute_swap_from_X(self, dX):
        """Swap algo when provided with dX>0
        We go from right to left on the curve and manage crossings as needed.
        within initialized tick we use swap_within_tick_from_X"""
        if dX <= 0.0:
            raise Exception("can only handle X being supplied to pool, dX>0")

        left_to_right = False

        # get current tick, current root price, and liquidity in range
        curr_rP = self.global_state.rP

        # main case where L_in range>0 , call swap_within_tick_from_X
        swapped_dX = 0.0
        swapped_dY = 0.0
        while swapped_dX < dX:
            if self.global_state.L > 0:
                next_tick = self.get_next_active_tick_left(starting_rP=curr_rP)
            else:
                # try move into range, if cannot break out to end swap
                next_tick, curr_rP = self.try_get_in_range(left_to_right=False)

            if next_tick is None:
                # there are no more active ticks on the left, terminate swap
                return swapped_dX, swapped_dY

            (done_dX, done_dY, end_rP, cross,) = self.swap_within_tick_from_X(
                start_rP=curr_rP,
                next_tick=next_tick,
                L=self.global_state.L,
                dX=dX - swapped_dX,
            )
            swapped_dX += done_dX
            swapped_dY += done_dY
            curr_rP = end_rP

            # assess where we are on curve post_swap
            tmp_tick = self.rP_to_possible_tick(curr_rP, left_to_right)
            # we shouldn't have changed tick yet before crossing is required
            assert tmp_tick == next_tick

            # update global state to reflect price change (if any)
            self.global_state.rP = curr_rP
            self.global_state.tick = next_tick

            if cross is True:
                self.cross_tick(
                    provided_tick=next_tick,
                    left_to_right=left_to_right,
                )

    def swap_within_tick_from_Y(self, *args):
        pass

    def execute_swap_from_Y(self, dY):
        pass
